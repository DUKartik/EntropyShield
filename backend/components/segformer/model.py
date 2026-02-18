import torch
from transformers import SegformerForSemanticSegmentation


def get_segformer_model(num_classes=2, pretrained=True, device=None):
    """
    Returns a SegFormer-B0 model configured for binary segmentation.

    Args:
        num_classes (int): Number of output classes (2 for tampered / clean)
        pretrained (bool): Load ImageNet + ADE pretrained weights
        device (str or torch.device): 'cuda' or 'cpu'

    Returns:
        model (torch.nn.Module)
    """

    model_name = "nvidia/segformer-b0-finetuned-ade-512-512"

    if pretrained:
        model = SegformerForSemanticSegmentation.from_pretrained(
            model_name,
            num_labels=num_classes,
            ignore_mismatched_sizes=True  # replaces ADE head safely
        )
    else:
        from transformers import SegformerConfig
        config = SegformerConfig.from_pretrained(model_name)
        config.num_labels = num_classes
        model = SegformerForSemanticSegmentation(config)

    # Optional: freeze encoder for warm-up training
    for param in model.segformer.encoder.parameters():
        param.requires_grad = False

    # Move to device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model.to(device)

    return model
