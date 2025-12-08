# app_langscale/utils/file_utils.py

def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate file extension
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions
        
    Returns:
        bool: True if file extension is allowed
    """
    return any(filename.lower().endswith(ext.lower()) for ext in allowed_extensions)