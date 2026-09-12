import os
import logging
from collections import defaultdict, deque
import json
import queue
import threading
from pathlib import Path
from time import monotonic
from dotenv import load_dotenv
from pydantic import ValidationError

from flask import Flask, Response, g, jsonify, render_template, request, redirect, session, stream_with_context, url_for, flash
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(dotenv_path=Path(__file__).resolve().with_name('.env'))

from models.evidence import Evidence, VerificationResult
from models.schemas import Verdict, VerificationReport, VerifyRequest
from verification_service import VerificationService
from db_manager import (
    DatabaseManager,
    init_db,
    save_claim,
    update_claim_status,
    save_verdict,
    save_evidence,
    get_all_claims,
    get_claim_by_id,
    get_stats,
)
from config import settings
from rag_memory import BerryLensMemory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = settings.flask_secret_key or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
_request_times = defaultdict(deque)
_metrics = defaultdict(int)


class LazyMemory:
    """Delay Chroma and embedding-model initialization until it is needed."""

    def __init__(self, path):
        self.path = str(path)
        self._instance = None

    @property
    def instance(self):
        if self._instance is None:
            self._instance = BerryLensMemory(self.path)
        return self._instance

    def search(self, *args, **kwargs):
        try:
            return self.instance.search(*args, **kwargs)
        except Exception:
            logger.warning("RAG search unavailable", exc_info=True)
            return []

    def store(self, *args, **kwargs):
        try:
            return self.instance.store(*args, **kwargs)
        except Exception:
            logger.warning("RAG store unavailable", exc_info=True)

    def count(self):
        if self._instance is not None:
            try:
                return self._instance.count()
            except Exception:
                return 0
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.path)
            return client.get_collection(name='fact_checks').count()
        except Exception:
            return 0


@app.before_request
def protect_api_gateway():
    g.request_started = monotonic()
    # API key gate — only active when BERRYLENS_API_KEY is set
    if settings.api_key and request.path in ('/check', '/api/verify', '/api/v1/verify', '/api/v1/verify/stream'):
        if request.headers.get('X-API-Key') != settings.api_key:
            return jsonify({'error': 'unauthorized'}), 401
    # Rate limiting on verify endpoints
    if request.path not in ('/check', '/api/verify', '/api/v1/verify', '/api/v1/verify/stream', '/verify'):
        return None
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
        elapsed = monotonic() - g.request_started
        _metrics['berrylens_request_duration_seconds_sum'] += elapsed
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


# ── Error handlers ──────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'not_found'}), 404
    return render_template('error.html', code=404, message='Page not found.'), 404


@app.errorhandler(429)
def rate_limited(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'rate_limit_exceeded'}), 429
    return render_template('error.html', code=429, message='Too many requests. Please wait a moment.'), 429


@app.errorhandler(500)
def server_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'internal_server_error'}), 500
    return render_template('error.html', code=500, message='Something went wrong. Please try again.'), 500


# ── Initialize services ──────────────────────────────────────────────────────

init_db()
memory = LazyMemory(settings.chroma_path)
report_db = DatabaseManager(settings.database_path)


def persist_report(report: VerificationReport, user_id=None):
    """Persist the new report through the existing relational schema."""
    report_db.save(report, user_id=user_id)
    claim_id = save_claim(report.claim)
    verdict_map = {
        Verdict.SUPPORTED: 'SUPPORTED',
        Verdict.REFUTED: 'REFUTED',
        Verdict.PARTIALLY_SUPPORTED: 'PARTIALLY_SUPPORTED',
        Verdict.INSUFFICIENT_EVIDENCE: 'INSUFFICIENT_EVIDENCE',
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


# ── Auth routes ──────────────────────────────────────────────────────────────

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


# ── Main routes ──────────────────────────────────────────────────────────────

@app.route('/')
def home():
    report_stats = report_db.stats(user_id=session.get('user_id'))
    stats = {
        'total_claims': report_stats['total'],
        'avg_confidence': round(float(report_stats['average_confidence']) * 100),
    }
    return render_template('index.html', stats=stats)


@app.route('/verify', methods=['POST'])
def verify():
    """Form submission endpoint — verifies claim and redirects to result page."""
    claim_text = request.form.get('claim', '').strip()
    if not claim_text:
        flash('Please enter a claim to verify.', 'error')
        return redirect(url_for('home'))
    if len(claim_text) < 10:
        flash('Please enter a more specific claim (at least 10 characters).', 'error')
        return redirect(url_for('home'))
    try:
        report = verification_service.verify(claim_text, user_id=session.get('user_id'))
        if report.id:
            return redirect(url_for('result', claim_id=report.id))
        return redirect(url_for('home'))
    except ValidationError as error:
        flash('The claim could not be validated. Please check your input.', 'error')
        return redirect(url_for('home'))
    except Exception:
        logger.exception('Form verification failed')
        flash('Verification failed. Please try again shortly.', 'error')
        return redirect(url_for('home'))


@app.route('/check', methods=['POST'])
@app.route('/api/verify', methods=['POST'])
@app.route('/api/v1/verify', methods=['POST'])
def check_claim():
    payload = request.get_json(silent=True) or {}
    try:
        request_model = VerifyRequest.model_validate(payload)
        report = verification_service.verify(request_model.claim, user_id=session.get('user_id'))
        return jsonify(report.model_dump(mode='json'))
    except ValidationError as error:
        return jsonify({'error': 'validation_error', 'detail': error.errors()}), 422
    except Exception:
        logger.exception('Verification pipeline failed')
        return jsonify({'error': 'pipeline_error', 'message': 'Verification could not be completed. Please try again.'}), 500


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
            report = verification_service.verify(request_model.claim, progress=progress, user_id=user_id)
            payload = report.model_dump(mode='json')
            events.put({'stage': 'completed', 'data': payload})
        except Exception:
            logger.exception('Streaming verification failed')
            events.put({'stage': 'error', 'data': {'error': 'pipeline_error', 'message': 'Verification could not be completed.'}})
        finally:
            events.put(finished)

    threading.Thread(target=run_pipeline, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            try:
                event = events.get(timeout=120)
            except queue.Empty:
                yield "event: error\ndata: {\"error\": \"timeout\"}\n\n"
                break
            if event is finished:
                break
            yield f"event: {event['stage']}\ndata: {json.dumps(event['data'])}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Result / History / Dashboard ─────────────────────────────────────────────

@app.route('/claim/<int:claim_id>')
def result(claim_id):
    report = report_db.get_by_id(claim_id, user_id=session.get('user_id'))
    if not report:
        flash('Claim not found.', 'error')
        return redirect(url_for('home'))
    return render_template('result.html', report=report)


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


# ── API routes ───────────────────────────────────────────────────────────────

@app.route('/api/v1/result/<int:report_id>')
@app.route('/api/reports/<int:report_id>')
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
        logger.warning('RAG memory count unavailable', exc_info=True)
        rag_count = 0
    return jsonify({
        'total': total,
        'supported_count': verdict_counts.get('supported', 0),
        'refuted_count': verdict_counts.get('refuted', 0),
        'partially_supported_count': verdict_counts.get('partially_supported', 0),
        'insufficient_evidence_count': verdict_counts.get('insufficient_evidence', 0),
        'avg_confidence': round(total_confidence / total) if total else 0,
        'true_rate': round((verdict_counts.get('supported', 0) / total) * 100) if total else 0,
        'verdict_counts': dict(verdict_counts),
        'confidence_buckets': {str(k): v for k, v in confidence_buckets.items()},
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
            'id': report.id,
            'text': report.claim,
            'verdict': report.verdict.value,
            'confidence': report.confidence_pct,
            'status': report.research_status.value,
            'created_at': report.timestamp.isoformat(),
        }
        for report in reports
    ]})


# ── Health / Metrics / Docs ───────────────────────────────────────────────────

@app.route('/health')
def health():
    components = {}
    overall = 'ok'

    # Database check
    try:
        report_db.stats()
        components['database'] = 'ok'
    except Exception as error:
        components['database'] = f'error: {type(error).__name__}'
        overall = 'degraded'

    # Provider availability
    providers = {}
    if settings.gemini_api_key:
        providers['gemini'] = 'configured'
    if settings.groq_api_key:
        providers['groq'] = 'configured'
    if settings.deepseek_api_key:
        providers['deepseek'] = 'configured'
    if settings.cerebras_api_key:
        providers['cerebras'] = 'configured'
    if not providers:
        overall = 'degraded'
    components['llm_providers'] = providers or 'none_configured'

    # Search provider
    if settings.tavily_api_key:
        components['search'] = 'configured'
    else:
        components['search'] = 'not_configured'
        overall = 'degraded'

    # RAG / Chroma (lazy — don't force-init)
    components['rag'] = 'lazy_init'

    return jsonify({
        'status': overall,
        'service': 'berrylens-ai',
        'primary_provider': settings.primary_llm_provider,
        'llm_disabled': settings.disable_llm,
        'components': components,
    }), 200 if overall == 'ok' else 207


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
        '# HELP berrylens_verifications_total Total verification attempts.',
        '# TYPE berrylens_verifications_total counter',
        f"berrylens_verifications_total {_metrics.get('berrylens_verifications_total', 0)}",
    ]
    return Response('\n'.join(lines) + '\n', mimetype='text/plain; version=0.0.4')


@app.route('/api/docs')
def api_docs():
    return jsonify({
        'openapi': '3.0.3',
        'info': {'title': 'BerryLens AI API', 'version': '1.0.0', 'description': 'Evidence-grounded claim verification API'},
        'paths': {
            '/api/v1/verify': {'post': {
                'summary': 'Verify a claim',
                'requestBody': {'content': {'application/json': {'schema': {'type': 'object', 'properties': {'claim': {'type': 'string', 'minLength': 10, 'maxLength': 1000}}, 'required': ['claim']}}}},
                'responses': {'200': {'description': 'Verification report'}, '422': {'description': 'Validation error'}, '429': {'description': 'Rate limited'}, '500': {'description': 'Pipeline error'}}
            }},
            '/api/v1/verify/stream': {'post': {'summary': 'Verify a claim with SSE progress events'}},
            '/api/v1/result/{id}': {'get': {'summary': 'Get a stored report by ID'}},
            '/api/v1/history': {'get': {'summary': 'List stored reports (authenticated)'}},
            '/api/v1/stats': {'get': {'summary': 'Get report statistics (authenticated)'}},
            '/api/stats': {'get': {'summary': 'Get aggregated stats (public)'}},
            '/api/history': {'get': {'summary': 'List recent reports (public, limited)'}},
            '/health': {'get': {'summary': 'Health check with component status'}},
            '/metrics': {'get': {'summary': 'Prometheus-compatible metrics'}},
        },
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
