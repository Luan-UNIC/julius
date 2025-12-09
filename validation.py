"""
FIDC Middleware - Validation Functions
=======================================

CPF and CNPJ validation with check digits.

Author: FIDC Development Team
Version: 1.0.0
"""


def validate_cpf(cpf: str) -> bool:
    """
    Validate Brazilian CPF (Cadastro de Pessoas Físicas).
    
    Args:
        cpf: CPF string (can contain formatting)
        
    Returns:
        True if valid, False otherwise
    """
    # Remove non-digit characters
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # CPF must have 11 digits
    if len(cpf) != 11:
        return False
    
    # Check for known invalid CPFs (all digits the same)
    if cpf == cpf[0] * 11:
        return False
    
    # Calculate first check digit
    sum_val = 0
    for i in range(9):
        sum_val += int(cpf[i]) * (10 - i)
    
    remainder = sum_val % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cpf[9]) != first_digit:
        return False
    
    # Calculate second check digit
    sum_val = 0
    for i in range(10):
        sum_val += int(cpf[i]) * (11 - i)
    
    remainder = sum_val % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cpf[10]) != second_digit:
        return False
    
    return True


def validate_cnpj(cnpj: str) -> bool:
    """
    Validate Brazilian CNPJ (Cadastro Nacional da Pessoa Jurídica).
    
    Args:
        cnpj: CNPJ string (can contain formatting)
        
    Returns:
        True if valid, False otherwise
    """
    # Remove non-digit characters
    cnpj = ''.join(filter(str.isdigit, cnpj))
    
    # CNPJ must have 14 digits
    if len(cnpj) != 14:
        return False
    
    # Check for known invalid CNPJs (all digits the same)
    if cnpj == cnpj[0] * 14:
        return False
    
    # Calculate first check digit
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = 0
    for i in range(12):
        sum_val += int(cnpj[i]) * weights1[i]
    
    remainder = sum_val % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cnpj[12]) != first_digit:
        return False
    
    # Calculate second check digit
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = 0
    for i in range(13):
        sum_val += int(cnpj[i]) * weights2[i]
    
    remainder = sum_val % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cnpj[13]) != second_digit:
        return False
    
    return True


def validate_cpf_cnpj(document: str) -> bool:
    """
    Validate CPF or CNPJ based on length.
    
    Args:
        document: CPF or CNPJ string (can contain formatting)
        
    Returns:
        True if valid, False otherwise
    """
    clean_doc = ''.join(filter(str.isdigit, document))
    
    if len(clean_doc) == 11:
        return validate_cpf(document)
    elif len(clean_doc) == 14:
        return validate_cnpj(document)
    else:
        return False


def format_cpf(cpf: str) -> str:
    """
    Format CPF with standard Brazilian formatting: 000.000.000-00
    
    Args:
        cpf: CPF string (digits only)
        
    Returns:
        Formatted CPF string
    """
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11:
        return cpf
    
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def format_cnpj(cnpj: str) -> str:
    """
    Format CNPJ with standard Brazilian formatting: 00.000.000/0000-00
    
    Args:
        cnpj: CNPJ string (digits only)
        
    Returns:
        Formatted CNPJ string
    """
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14:
        return cnpj
    
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
