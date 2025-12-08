"""
FIDC Middleware - Utility Functions
====================================

Helper functions for CNAB and boleto generation.

Author: FIDC Development Team
Version: 1.0.0
"""

from typing import Union


def calcular_dv_bmp(carteira: Union[str, int], nosso_numero_sem_dv: Union[str, int]) -> str:
    """
    Calculate BMP Money Plus check digit (DV) for Nosso Número.
    
    Uses modulo 11 with base 7 (weights from 2 to 7) as specified in
    BMP CNAB 400 manual (pages 13-14).
    
    Algorithm:
    1. Concatenate carteira + nosso_numero (11 digits)
    2. Apply weights 2-7 from right to left, cycling
    3. Sum all products
    4. Calculate remainder = sum % 11
    5. Apply remainder rules:
       - If remainder == 0: DV = '0'
       - If remainder == 1: DV = 'P'
       - Otherwise: DV = str(11 - remainder)
    
    Args:
        carteira: Wallet code (e.g., '109', '1')
        nosso_numero_sem_dv: Sequential number without check digit
        
    Returns:
        Check digit as string ('0'-'9' or 'P')
        
    Example:
        >>> calcular_dv_bmp('109', '1')
        '0'
        >>> calcular_dv_bmp('1', '00000000001')
        'P'
    """
    # Ensure nosso_numero is 11 characters (zero-padded)
    nn_str = str(nosso_numero_sem_dv).zfill(11)
    
    # Concatenate carteira + nosso_numero
    base_calculo = str(carteira) + nn_str
    
    soma = 0
    peso = 2
    
    # Loop from right to left applying weights 2-7
    for digito in reversed(base_calculo):
        soma += int(digito) * peso
        peso += 1
        if peso > 7:  # Cycle weights: 2, 3, 4, 5, 6, 7, 2, 3, ...
            peso = 2
    
    resto = soma % 11
    
    # Apply remainder rules as per BMP specification
    if resto == 0:
        dv = '0'
    elif resto == 1:
        dv = 'P'  # Special case: P indicates remainder 1
    else:
        dv = str(11 - resto)
    
    return dv
