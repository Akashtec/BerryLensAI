"""Optional LIAR/CSV prior-classifier training utility.

This model is an auxiliary prior only. It must never replace retrieved evidence.
The LIAR dataset is political, short-form, and domain-specific; results do not
represent general factuality or production verification accuracy.
"""

import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Train an optional DistilBERT prior classifier")
    parser.add_argument('--dataset-path', required=True, help='CSV/JSON dataset path with text and label columns')
    parser.add_argument('--output-dir', default='models/prior_classifier')
    parser.add_argument('--text-column', default='statement')
    parser.add_argument('--label-column', default='label')
    parser.add_argument('--epochs', type=int, default=2)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--learning-rate', type=float, default=5e-5)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        from datasets import load_dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments
    except ImportError as error:
        raise SystemExit('Install optional training dependencies: pip install datasets transformers torch') from error

    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        raise SystemExit(f'Dataset not found: {dataset_path}')
    extension = dataset_path.suffix.lower().lstrip('.')
    dataset = load_dataset('csv' if extension == 'csv' else 'json', data_files=str(dataset_path), split='train')
    labels = sorted(set(dataset[args.label_column]))
    label_to_id = {label: index for index, label in enumerate(labels)}
    dataset = dataset.map(lambda row: {'labels': label_to_id[row[args.label_column]]})
    tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
    tokenized = dataset.map(lambda batch: tokenizer(batch[args.text_column], truncation=True, padding='max_length', max_length=256), batched=True)
    model = AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased', num_labels=len(labels))
    output_dir = Path(args.output_dir)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        evaluation_strategy='no',
        save_strategy='epoch',
        report_to='none',
    )
    Trainer(model=model, args=training_args, train_dataset=tokenized, tokenizer=tokenizer).train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / 'label_map.json').write_text(str(label_to_id), encoding='utf-8')
    print(f'Saved auxiliary prior classifier to {output_dir}')


if __name__ == '__main__':
    main()
