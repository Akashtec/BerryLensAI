import os
import importlib.util
from collections import defaultdict, deque
import json
import queue
import threading
from pathlib import Path
from time import monotonic
from dotenv import load_dotenv
from collections import defaultdict
from pydantic import ValidationError

from flask import Flask, Response, g, jsonify, render_template, request, redirect, session, stream_with_context, url_for, flash
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(dotenv_path=Path(__file__).resolve().with_name('.env'))

from models.evidence import Evidence, VerificationResult
from models.schemas import Verdict, VerificationReport, VerifyRequest
from verification_service import VerificationService
_db_spec = importlib.util.spec_from_file_location(
    'berrylens_db', Path(__file__).parent / 'db_manager.py' / 'db_manager.py'
)
db_module = importlib.util.module_from_spec(_db_spec)
_db_spec.loader.exec_module(db_module)
init_db = db_module.init_db
save_claim = db_module.save_claim
update_claim_status = db_module.update_claim_status
save_verdict = db_module.save_verdict
save_evidence = db_module.save_evidence
get_all_claims = db_module.get_all_claims
get_claim_by_id = db_module.get_claim_by_id
get_stats = db_module.get_stats
from config import settings
from rag_memory import BerryLensMemory

app = Flask(__name__)
app.secret_key = settings.flask_secret_key or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
_request_times = defaultdict(deque)
_metrics = defaultdict(int)


class LazyMemory:
    """Delay Chroma and embedding-model initialization until it is needed."""

    def __init__(self, path):
        self.path = path
        self._instance = None

    @property
    def instance(self):
        if self._instance is None:
            self._instance = BerryLensMemory(self.path)
        return self._instance

    def search(self, *args, **kwargs):
        return self.instance.search(*args, **kwargs)

    def store(self, *args, **kwargs):
        return self.instance.store(*args, **kwargs)

    def count(self):
        if self._instance is not None:
            return self._instance.count()
        try:
            import chromadb

            client = chromadb.PersistentClient(path=self.path)
            return client.get_collection(name='fact_checks').count()
        except Exception:
            return 0


@app.before_request
def protect_api_gateway():
    g.request_started = monotonic()
    if request.path not in ('/check', '/api/v1/verify', '/api/v1/verify/stream'):
        return None
    if settings.api_key and request.headers.get('X-API-Key') != settings.api_key:
        return jsonify({'error': 'unauthorized'}), 401
    now = monotonic()
    bucket = _request_times[request.remote_addr or 'unknown']
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return jsonify({'error': 'rate_limit_exceeded', 'retry_after': 60}), 429
    bucket.append(now)
    return None


@app.after_request
def add_security_headers(response):
    _metrics['berrylens_requests_total'] += 1
    _metrics[f"berrylens_http_status_total{{status=\"{response.status_code}\"}}"] += 1
    if response.status_code >= 400:
        _metrics['berrylens_api_errors_total'] += 1
    if hasattr(g, 'request_started'):
        _metrics['berrylens_request_duration_seconds_sum'] += monotonic() - g.request_started
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/') or request.path == '/profile':
                return jsonify({'error': 'authentication_required'}), 401
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped

# Initialize DB on startup
init_db()
memory = LazyMemory(settings.chroma_path)
report_db = db_module.DatabaseManager(settings.database_path)
 

def persist_report(report: VerificationReport, user_id=None):
    """Persist the new report through the existing relational schema."""
    report_db.save(report, user_id=user_id)
    claim_id = save_claim(report.claim)
    verdict_map = {
        Verdict.TRUE: 'SUPPORTED',
        Verdict.FALSE: 'REFUTED',
        Verdict.MIXED: 'INSUFFICIENT EVIDENCE',
        Verdict.UNCERTAIN: 'INSUFFICIENT EVIDENCE',
        Verdict.ERROR: 'INSUFFICIENT EVIDENCE',
    }
    verdict_id = save_verdict(
        claim_id,
        VerificationResult(
            verdict=verdict_map[report.verdict],
            confidence=report.confidence_pct,
            explanation=report.summary,
        ),
    )
    save_evidence(
        verdict_id,
        [
            Evidence(
                title=item.source.title,
                url=str(item.source.url),
                snippet=item.relevant_passage,
                source=item.source.domain,
                query=report.search_queries_used[0] if report.search_queries_used else report.claim,
            )
            for item in report.all_evidence
        ],
    )
    update_claim_status(claim_id, 'completed')
    if report.research_status.value not in ('FAILED', 'CACHED'):
        memory.store(report.claim, {
        'verdict': report.verdict.value,
        'confidence': report.confidence_pct,
        'summary': report.summary,
        'research_status': report.research_status.value,
        'schema_version': report.schema_version,
        'sources': [
            {'title': item.source.title, 'url': str(item.source.url)}
            for item in report.all_evidence[:3]
        ],
        })
    return claim_id


verification_service = VerificationService(memory=memory, persist=persist_report)


@app.route('/')
def home():
    report_stats = report_db.stats(user_id=session.get('user_id'))
    stats = {
        'total_claims': report_stats['total'],
        'avg_confidence': round(float(report_stats['average_confidence']) * 100),
    }
    return render_template('index.html', stats=stats)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return jsonify({'endpoint': 'register', 'method': 'POST'})
    payload = request.get_json(silent=True) or request.form
    email = str(payload.get('email', '')).strip().lower()
    password = str(payload.get('password', ''))
    if '@' not in email or len(password) < 8:
        return jsonify({'error': 'validation_error', 'detail': 'Valid email and password of at least 8 characters required'}), 422
    if report_db.get_user_by_email(email):
        return jsonify({'error': 'email_already_registered'}), 409
    user_id = report_db.create_user(email, generate_password_hash(password))
    session['user_id'] = user_id
    return jsonify({'user_id': user_id, 'email': email}), 201


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return jsonify({'endpoint': 'login', 'method': 'POST'})
    payload = request.get_json(silent=True) or request.form
    email = str(payload.get('email', '')).strip().lower()
    user = report_db.get_user_by_email(email)
    if not user or not check_password_hash(user['password_hash'], str(payload.get('password', ''))):
        return jsonify({'error': 'invalid_credentials'}), 401
    session['user_id'] = user['id']
    return jsonify({'user_id': user['id'], 'email': user['email']})


@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return jsonify({'status': 'logged_out'})


@app.route('/profile')
@login_required
def profile():
    user = report_db.get_user(session['user_id'])
    return jsonify({'id': user['id'], 'email': user['email'], 'created_at': user['created_at']})


@app.route('/verify', methods=['POST'])
def verify():
    claim_text = request.form.get('claim', '').strip()
    if not claim_text:
        flash('Please enter a claim to verify.', 'error')
        return redirect(url_for('home'))
    try:
        try:
            report = verification_service.verify(claim_text, user_id=session.get('user_id'))
        except TypeError:
            report = verification_service.verify(claim_text)
        return jsonify(report.model_dump(mode='json'))
    except ValidationError as error:
        return jsonify({'error': 'validation_error', 'detail': error.errors()}), 422
    except Exception:
        app.logger.exception('Form verification failed')
        return jsonify({'error': 'pipeline_error'}), 500


@app.route('/check', methods=['POST'])
@app.route('/api/v1/verify', methods=['POST'])
def check_claim():

    payload = request.get_json(silent=True) or {}
    try:
        request_model = VerifyRequest.model_validate(payload)
        try:
            report = verification_service.verify(request_model.claim, user_id=session.get('user_id'))
        except TypeError:
            report = verification_service.verify(request_model.claim)
        return jsonify(report.model_dump(mode='json'))
    except ValidationError as error:
        return jsonify({'error': 'validation_error', 'detail': error.errors()}), 422
    except Exception:
        app.logger.exception('Verification pipeline failed')
        return jsonify({'error': 'pipeline_error'}), 500


@app.route('/api/v1/verify/stream', methods=['POST'])
def verify_stream():
    payload = request.get_json(silent=True) or {}
    try:
        request_model = VerifyRequest.model_validate(payload)
    except ValidationError as error:
        return jsonify({'error': 'validation_error', 'detail': error.errors()}), 422

    events = queue.Queue()
    finished = object()
    user_id = session.get('user_id')

    def progress(stage, data):
        events.put({'stage': stage, 'data': data})

    def run_pipeline():
        try:
            try:
                report = verification_service.verify(request_model.claim, progress=progress, user_id=user_id)
            except TypeError:
                report = verification_service.verify(request_model.claim, progress=progress)
            events.put({'stage': 'completed', 'data': report.model_dump(mode='json')})
        except Exception:
            app.logger.exception('Streaming verification failed')
            events.put({'stage': 'error', 'data': {'error': 'pipeline_error'}})
        finally:
            events.put(finished)

    threading.Thread(target=run_pipeline, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            event = events.get()
            if event is finished:
                break
            yield f"event: {event['stage']}\ndata: {json.dumps(event['data'])}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'berrylens-ai',
        'database': 'available',
        'huggingface': 'configured' if settings.huggingface_api_key else 'not_configured',
        'tavily': 'configured' if settings.tavily_api_key else 'not_configured',
        'chroma': 'optional_lazy',
    })


@app.route('/metrics')
def metrics():
    lines = [
        '# HELP berrylens_requests_total Total HTTP requests.',
        '# TYPE berrylens_requests_total counter',
        f"berrylens_requests_total {_metrics['berrylens_requests_total']}",
        '# HELP berrylens_api_errors_total HTTP responses with error status.',
        '# TYPE berrylens_api_errors_total counter',
        f"berrylens_api_errors_total {_metrics['berrylens_api_errors_total']}",
        '# HELP berrylens_request_duration_seconds_sum Cumulative request duration.',
        '# TYPE berrylens_request_duration_seconds_sum counter',
        f"berrylens_request_duration_seconds_sum {_metrics['berrylens_request_duration_seconds_sum']:.6f}",
    ]
    return Response('\n'.join(lines) + '\n', mimetype='text/plain; version=0.0.4')


@app.route('/api/docs')
def api_docs():
    return jsonify({
        'openapi': '3.0.3',
        'info': {'title': 'BerryLens AI API', 'version': '1.0.0'},
        'paths': {
            '/api/v1/verify': {'post': {'summary': 'Verify a claim'}},
            '/api/v1/verify/stream': {'post': {'summary': 'Verify a claim with SSE progress'}},
            '/api/v1/result/{id}': {'get': {'summary': 'Get a stored report'}},
            '/api/v1/history': {'get': {'summary': 'List stored reports'}},
            '/api/v1/stats': {'get': {'summary': 'Get report statistics'}},
            '/health': {'get': {'summary': 'Health check'}},
            '/metrics': {'get': {'summary': 'Prometheus-compatible metrics'}},
        },
    })


@app.route('/claim/<int:claim_id>')
def result(claim_id):
    report = report_db.get_by_id(claim_id, user_id=session.get('user_id'))
    if not report:
        flash('Claim not found.', 'error')
        return redirect(url_for('home'))
    return render_template('result.html', report=report)


@app.route('/api/v1/result/<int:report_id>')
@login_required
def api_result(report_id):
    report = report_db.get_by_id(report_id, user_id=session['user_id'])
    if report is None:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(report.model_dump(mode='json'))


@app.route('/api/v1/history')
@login_required
def api_v1_history():
    try:
        limit = max(1, min(int(request.args.get('limit', 20)), 100))
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        return jsonify({'error': 'validation_error', 'detail': 'limit and offset must be integers'}), 422
    reports = report_db.list_reports(limit=limit, offset=offset, user_id=session['user_id'])
    return jsonify({'reports': [report.model_dump(mode='json') for report in reports]})


@app.route('/api/v1/stats')
@login_required
def api_v1_stats():
    return jsonify(report_db.stats(user_id=session['user_id']))


@app.route('/history')
def history():
    claims = [
        {
            'id': report.id,
            'text': report.claim,
            'verdict': report.verdict.value,
            'confidence': report.confidence_pct,
            'status': report.research_status.value,
            'created_at': report.timestamp.isoformat(),
        }
        for report in report_db.list_reports(user_id=session.get('user_id'))
    ]
    return render_template('history.html', claims=claims)


@app.route('/dashboard')
def dashboard():
    stats = report_db.stats(user_id=session.get('user_id'))
    claims = [
        {
            'id': report.id,
            'text': report.claim,
            'verdict': report.verdict.value,
            'confidence': report.confidence_pct,
            'status': report.research_status.value,
            'created_at': report.timestamp.isoformat(),
        }
        for report in report_db.list_reports(limit=20, user_id=session.get('user_id'))
    ]
    return render_template('dashboard.html', stats=stats, claims=claims)


@app.route('/api/stats')
def api_stats():
    reports = report_db.list_reports(user_id=session.get('user_id'))
    verdict_counts = defaultdict(int)
    confidence_buckets = defaultdict(int)
    timeline = defaultdict(int)
    total_confidence = 0

    for report in reports:
        verdict = report.verdict.value.lower()
        verdict_counts[verdict] += 1
        confidence = report.confidence_pct
        total_confidence += confidence
        confidence_buckets[min(confidence // 20, 4)] += 1
        timestamp = report.timestamp.isoformat()
        timeline[str(timestamp)[:10]] += 1

    total = len(reports)
    try:
        rag_count = memory.count()
    except Exception:
        app.logger.exception('RAG memory count unavailable')
        rag_count = 0
    return jsonify({
        'total': total,
        'true_count': verdict_counts.get('true', 0),
        'false_count': verdict_counts.get('false', 0),
        'mixed_count': verdict_counts.get('mixed', 0),
        'unknown_count': verdict_counts.get('uncertain', 0) + verdict_counts.get('error', 0),
        'avg_confidence': round(total_confidence / total) if total else 0,
        'true_rate': round((verdict_counts.get('supported', 0) / total) * 100) if total else 0,
        'verdict_counts': dict(verdict_counts),
        'confidence_buckets': dict(confidence_buckets),
        'timeline': dict(sorted(timeline.items())),
        'rag_count': rag_count,
    })


@app.route('/api/history')
def api_history():
    try:
        limit = max(1, min(int(request.args.get('limit', 20)), 100))
    except ValueError:
        limit = 20
    reports = report_db.list_reports(limit=limit, user_id=session.get('user_id'))
    return jsonify({'claims': [
        {
            'text': report.claim,
            'verdict': report.verdict.value,
            'confidence': report.confidence_pct,
            'status': report.research_status.value,
            'created_at': report.timestamp.isoformat(),
        }
        for report in reports
    ]})


if __name__ == '__main__':
    app.run(debug=True, port=5000)