"""Model architecture for email categorization."""

import logging
from pathlib import Path
from typing import Dict, Optional
import json

import torch
import torch.nn as nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from peft import get_peft_model, LoraConfig, TaskType, PeftModel
import torch.nn.functional as F
import torch.quantization

logger = logging.getLogger(__name__)

class EmailCategorizationModel:
    """Email categorization model with LoRA fine-tuning and quantization."""
    
    def __init__(
        self,
        model_name: str,
        num_labels: int,
        device: str = 'mps',
        lora_r: int = 8,
        lora_alpha: int = 16,
        lora_dropout: float = 0.1
    ):
        """Initialize the model.
        
        Args:
            model_name: Name of the base model to use
            num_labels: Number of classification labels
            device: Device to run on ('mps', 'cuda', or 'cpu')
            lora_r: LoRA attention dimension
            lora_alpha: LoRA alpha parameter
            lora_dropout: LoRA dropout rate
        """
        self.device = device
        self.model_name = model_name
        self.num_labels = num_labels
        
        # Load and configure tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        # Set padding token to EOS token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Load base model
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=num_labels,
            torch_dtype=torch.float32,  # Use float32 for training
            pad_token_id=self.tokenizer.pad_token_id
        )
        
        # Add LoRA adapters
        peft_config = LoraConfig(
            task_type=TaskType.SEQ_CLS,
            inference_mode=False,
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=['q_proj', 'v_proj']  # Updated for Phi-2
        )
        self.model = get_peft_model(self.model, peft_config)
        
        # Move model to device
        self.model.to(device)
        
        logger.info(
            f"Initialized {model_name} with {self.model.num_parameters():,} parameters "
            f"({self.model.num_parameters(only_trainable=True):,} trainable)"
        )
    
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        labels: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """Forward pass through the model."""
        # Convert input tensors to the right type
        input_ids = input_ids.to(dtype=torch.long, device=self.device)
        attention_mask = attention_mask.to(dtype=torch.float32, device=self.device)
        if labels is not None:
            labels = labels.to(dtype=torch.long, device=self.device)
        
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )
        
        return {
            'loss': outputs.loss if labels is not None else None,
            'logits': outputs.logits,
            'predictions': torch.argmax(outputs.logits, dim=-1)
        }
    
    def save(self, output_dir: Path) -> None:
        """Save the model and tokenizer."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        self.model.save_pretrained(output_dir)
        
        # Save tokenizer
        self.tokenizer.save_pretrained(output_dir)
        
        # Save config with num_labels
        config = {
            "num_labels": self.num_labels,
            "model_name": self.model_name
        }
        with open(output_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Saved model and tokenizer to {output_dir}")
    
    def quantize(self, output_dir: Path) -> None:
        """Quantize the model to int8 for efficient inference.
        
        This creates a separate quantized version of the model.
        """
        output_dir = Path(output_dir)
        quant_dir = output_dir / "quantized"
        quant_dir.mkdir(parents=True, exist_ok=True)
        
        # Merge LoRA weights with base model
        self.model.merge_and_unload()
        
        # Move to CPU for quantization
        model = self.model.to('cpu')
        
        # Configure quantization
        model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
        
        # Prepare for quantization
        model_prepared = torch.quantization.prepare(model)
        
        # Calibrate with a few batches of data (dummy data here)
        model_prepared(
            torch.randint(0, 1000, (1, 128)),
            torch.ones(1, 128)
        )
        
        # Convert to quantized model
        quantized_model = torch.quantization.convert(model_prepared)
        
        # Save quantized model
        torch.save(quantized_model.state_dict(), quant_dir / "model.pt")
        self.tokenizer.save_pretrained(quant_dir)
        
        logger.info(f"Saved quantized model to {quant_dir}")
    
    @classmethod
    def load(cls, model_dir: Path, device: str = 'cpu') -> 'EmailCategorizationModel':
        """Load a saved model.
        
        Args:
            model_dir: Directory containing the saved model
            device: Device to load the model on
            
        Returns:
            Loaded model
        """
        model_dir = Path(model_dir)
        
        # Load model config to get num_labels
        config_path = model_dir / "config.json"
        with open(config_path, "r") as f:
            config = json.loads(f.read())
            num_labels = config["num_labels"]
        
        # Load base model with correct num_labels
        model = AutoModelForSequenceClassification.from_pretrained(
            "microsoft/phi-2",
            num_labels=num_labels,
            torch_dtype=torch.float32,
            pad_token_id=0  # Will be updated when we load tokenizer
        )
        
        # Load adapter weights
        model = PeftModel.from_pretrained(model, model_dir)
        
        # Create instance
        instance = cls(
            model_name=str(model_dir),
            num_labels=num_labels,
            device=device
        )
        
        # Load saved weights
        instance.model = model.to(device)
        instance.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        
        return instance 