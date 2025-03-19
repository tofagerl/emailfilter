"""Command line interface for training email classifiers."""

import sys
import logging
import argparse
from pathlib import Path

from ..inference.models import Account, Category
from .trainer import ModelTrainer
from .data import EmailDataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def handle_train_command(args):
    """Handle the train command."""
    try:
        # Create trainer
        trainer = ModelTrainer(
            model_name=args.model_name,
            output_dir=args.model_dir,
            device=args.device
        )
        
        # Create dataset
        dataset = EmailDataset(
            data_dir=args.data_dir,
            max_length=args.max_length
        )
        
        # Train model
        trainer.train(
            dataset=dataset,
            batch_size=args.batch_size,
            epochs=args.num_epochs,
            learning_rate=args.learning_rate,
            warmup_steps=args.warmup_steps
        )
    except Exception as e:
        logger.error(f"Error training model: {e}")
        sys.exit(1)

def handle_evaluate_command(args):
    """Handle the evaluate command."""
    try:
        # Create trainer
        trainer = ModelTrainer.load(
            model_dir=args.model_dir,
            device=args.device
        )
        
        # Create dataset
        dataset = EmailDataset(
            data_dir=args.test_dir,
            max_length=args.max_length
        )
        
        # Set tokenizer for dataset
        dataset.tokenizer = trainer.model.tokenizer
        
        # Evaluate model
        metrics = trainer.evaluate(dataset)
        
        # Print metrics
        print("\nEvaluation Results:")
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"Macro F1: {metrics['macro_f1']:.4f}")
        print(f"Weighted F1: {metrics['weighted_f1']:.4f}")
    except Exception as e:
        logger.error(f"Error evaluating model: {e}")
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Train and evaluate email classifiers")
    
    # Add version argument
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version information"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train a new model")
    train_parser.add_argument(
        "--model-name",
        type=str,
        default="microsoft/phi-2",
        help="Name of the model to use"
    )
    train_parser.add_argument(
        "--model-dir",
        type=str,
        required=True,
        help="Directory to save model checkpoints"
    )
    train_parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing training data"
    )
    train_parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device to use for training"
    )
    train_parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for training"
    )
    train_parser.add_argument(
        "--num-epochs",
        type=int,
        default=3,
        help="Number of epochs to train for"
    )
    train_parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-5,
        help="Learning rate for training"
    )
    train_parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.01,
        help="Weight decay for training"
    )
    train_parser.add_argument(
        "--warmup-steps",
        type=int,
        default=500,
        help="Number of warmup steps"
    )
    train_parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Maximum sequence length"
    )
    train_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed"
    )
    train_parser.set_defaults(func=handle_train_command)
    
    # Evaluate command
    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate a trained model")
    evaluate_parser.add_argument(
        "--model-name",
        type=str,
        default="microsoft/phi-2",
        help="Name of the model to use"
    )
    evaluate_parser.add_argument(
        "--model-dir",
        type=str,
        required=True,
        help="Directory containing model checkpoints"
    )
    evaluate_parser.add_argument(
        "--test-dir",
        type=str,
        required=True,
        help="Directory containing test data"
    )
    evaluate_parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device to use for evaluation"
    )
    evaluate_parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for evaluation"
    )
    evaluate_parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Maximum sequence length"
    )
    evaluate_parser.set_defaults(func=handle_evaluate_command)
    
    args = parser.parse_args()
    
    if args.version:
        from .. import __version__
        print(f"mailmind v{__version__}")
        sys.exit(0)
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main() 