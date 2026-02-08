import re
    
MAILS_FILE = 'api\\database\\tem_mail_registeration.json'

# function that validates email format
def validate_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.fullmatch(pattern, email) is not None
