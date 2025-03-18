"""Command line interface for training and evaluation."""

import logging
from pathlib import Path

import click
from transformers import AutoTokenizer

from .trainer import ModelTrainer
from .data import EmailDataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@click.group()
def train():
    """Train and evaluate email categorization models."""
    pass

@train.command()
@click.option(
    '--data-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Directory containing categorized email files'
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Directory to save model artifacts'
)
@click.option(
    '--model',
    type=str,
    default='microsoft/phi-2',
    help='Base model to use'
)
@click.option(
    '--device',
    type=str,
    default='mps',
    help='Device to train on (mps, cuda, or cpu)'
)
@click.option(
    '--epochs',
    type=int,
    default=3,
    help='Number of training epochs'
)
@click.option(
    '--batch-size',
    type=int,
    default=2,
    help='Training batch size'
)
@click.option(
    '--learning-rate',
    type=float,
    default=2e-4,
    help='Learning rate'
)
def start(
    data_dir: Path,
    output_dir: Path,
    model: str,
    device: str,
    epochs: int,
    batch_size: int,
    learning_rate: float
):
    """Train a new model."""
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize dataset and trainer
    dataset = EmailDataset(str(data_dir))
    trainer = ModelTrainer(model, output_dir, device)
    
    # Train model
    trainer.train(
        dataset=dataset,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate
    )
    
    # Save final model
    trainer.save_and_quantize()

@train.command()
@click.option(
    '--model-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Directory containing the model to evaluate'
)
@click.option(
    '--test-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Directory containing test emails'
)
@click.option(
    '--device',
    type=str,
    default='cpu',
    help='Device to evaluate on (mps, cuda, or cpu)'
)
def evaluate(model_dir: Path, test_dir: Path, device: str):
    """Evaluate a trained model."""
    # Load dataset
    dataset = EmailDataset(str(test_dir))
    
    # Load trainer with model
    trainer = ModelTrainer.load(str(model_dir), device)
    
    # Set tokenizer for dataset
    dataset.tokenizer = trainer.model.tokenizer
    
    # Evaluate
    metrics = trainer.evaluate(dataset)
    
    # Print metrics
    print("\nEvaluation Results:")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"Weighted F1: {metrics['weighted_f1']:.4f}")

if __name__ == '__main__':
    train() 