"""Training loop and metrics for email categorization."""

import logging
from pathlib import Path
from typing import Dict, Optional
from tqdm import tqdm

import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import classification_report

from .model import EmailCategorizationModel
from .data import EmailDataset

logger = logging.getLogger(__name__)

class ModelTrainer:
    """Trainer for email categorization models."""
    
    def __init__(
        self,
        model_name: str,
        output_dir: Path,
        device: str = 'mps'
    ):
        """Initialize the trainer.
        
        Args:
            model_name: Name of the base model to use
            output_dir: Directory to save model artifacts
            device: Device to train on
        """
        self.output_dir = Path(output_dir)
        self.device = device
        self.model_name = model_name
        self.model = None  # Initialized during training
    
    def train(
        self,
        dataset: EmailDataset,
        batch_size: int = 2,
        epochs: int = 3,
        learning_rate: float = 2e-4,
        warmup_steps: int = 100,
        eval_steps: int = 100,
        save_steps: int = 500
    ) -> None:
        """Train the model.
        
        Args:
            dataset: Training dataset
            batch_size: Training batch size
            epochs: Number of training epochs
            learning_rate: Learning rate
            warmup_steps: Number of warmup steps
            eval_steps: Steps between evaluations
            save_steps: Steps between saving checkpoints
        """
        # Initialize model
        if self.model is None:
            self.model = EmailCategorizationModel(
                model_name=self.model_name,
                num_labels=len(dataset.category_to_id),
                device=self.device
            )
        
        # Set up data loader
        dataset.tokenizer = self.model.tokenizer
        train_loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0  # Required for MPS
        )
        
        # Set up optimizer and scheduler
        optimizer = AdamW(
            self.model.model.parameters(),
            lr=learning_rate,
            weight_decay=0.01
        )
        scheduler = CosineAnnealingLR(
            optimizer,
            T_max=len(train_loader) * epochs
        )
        
        # Training loop
        global_step = 0
        best_accuracy = 0.0
        
        for epoch in range(epochs):
            self.model.model.train()
            epoch_loss = 0.0
            
            with tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}") as pbar:
                for batch in pbar:
                    # Move batch to device
                    batch = {k: v.to(self.device) for k, v in batch.items()}
                    
                    # Forward pass
                    outputs = self.model.forward(**batch)
                    loss = outputs['loss']
                    
                    # Backward pass
                    loss.backward()
                    optimizer.step()
                    scheduler.step()
                    optimizer.zero_grad()
                    
                    # Update metrics
                    epoch_loss += loss.item()
                    global_step += 1
                    
                    # Update progress bar
                    pbar.set_postfix({
                        'loss': f"{loss.item():.4f}",
                        'lr': f"{scheduler.get_last_lr()[0]:.2e}"
                    })
                    
                    # Evaluate and save
                    if global_step % eval_steps == 0:
                        metrics = self.evaluate(dataset)
                        accuracy = metrics['accuracy']
                        
                        # Save best model
                        if accuracy > best_accuracy:
                            best_accuracy = accuracy
                            self.save(is_best=True)
                        
                        # Log metrics
                        logger.info(
                            f"Step {global_step} | "
                            f"Loss: {loss.item():.4f} | "
                            f"Accuracy: {accuracy:.4f}"
                        )
                    
                    # Save checkpoint
                    if global_step % save_steps == 0:
                        self.save(is_best=False)
            
            # Log epoch metrics
            epoch_loss /= len(train_loader)
            logger.info(
                f"Epoch {epoch+1}/{epochs} | "
                f"Loss: {epoch_loss:.4f} | "
                f"Best Accuracy: {best_accuracy:.4f}"
            )
    
    def evaluate(self, dataset: EmailDataset) -> Dict[str, float]:
        """Evaluate the model.
        
        Args:
            dataset: Dataset to evaluate on
            
        Returns:
            Dictionary of metrics
        """
        self.model.model.eval()
        
        # Set up data loader
        dataset.tokenizer = self.model.tokenizer
        eval_loader = DataLoader(
            dataset,
            batch_size=8,
            shuffle=False,
            num_workers=0
        )
        
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in eval_loader:
                # Move batch to device
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                # Forward pass
                outputs = self.model.forward(**batch)
                
                # Collect predictions and labels
                all_preds.extend(outputs['predictions'].cpu().numpy())
                all_labels.extend(batch['labels'].cpu().numpy())
        
        # Get unique labels
        unique_labels = sorted(set(all_labels))
        label_names = [dataset.id_to_category[i] for i in unique_labels]
        
        # Calculate metrics
        report = classification_report(
            all_labels,
            all_preds,
            target_names=label_names,
            labels=unique_labels,
            output_dict=True
        )
        
        return {
            'accuracy': report['accuracy'],
            'macro_f1': report['macro avg']['f1-score'],
            'weighted_f1': report['weighted avg']['f1-score']
        }
    
    def save(self, is_best: bool = False) -> None:
        """Save the model.
        
        Args:
            is_best: Whether this is the best model so far
        """
        save_dir = self.output_dir / ('best' if is_best else 'latest')
        self.model.save(save_dir)
        
        if is_best:
            logger.info(f"Saved best model to {save_dir}")
    
    def save_and_quantize(self) -> None:
        """Save the final model."""
        # Save final model
        final_dir = self.output_dir / 'final'
        self.model.save(final_dir)
        logger.info(f"Saved final model to {final_dir}")
    
    @classmethod
    def load(cls, model_dir: str, device: str = 'cpu') -> 'ModelTrainer':
        """Load a saved model.
        
        Args:
            model_dir: Directory containing the saved model
            device: Device to load the model on
            
        Returns:
            Loaded trainer
        """
        model_dir = Path(model_dir)
        trainer = cls(
            model_name=str(model_dir),
            output_dir=model_dir,  # Use model_dir as output_dir
            device=device
        )
        trainer.model = EmailCategorizationModel.load(model_dir, device)
        return trainer 