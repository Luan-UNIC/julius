def calcular_dv_bmp(carteira, nosso_numero_sem_dv):
    """
    Calcula o Dígito Verificador (DV) do Nosso Número para o Banco BMP.
    Regra: Base 7 (pesos 2 a 7).
    """
    # Manual Pag 13: "Acrescentar a carteira à esquerda antes do Nosso Número"
    # Ex: Carteira '1' e Nosso Numero '00000000001' -> '100000000001'
    # Ensure nossonumero is 11 chars
    nn_str = str(nosso_numero_sem_dv).zfill(11)
    base_calculo = str(carteira) + nn_str
    
    soma = 0
    peso = 2
    
    # Loop reverso (da direita para a esquerda)
    for digito in reversed(base_calculo):
        soma += int(digito) * peso
        peso += 1
        if peso > 7: # Manual diz "base 7"
            peso = 2
            
    resto = soma % 11
    
    # Regra do Resto (Pag 13 e 14)
    if resto == 0:
        dv = '0'
    elif resto == 1:
        dv = 'P' # Manual Pag 13: Se resto 1, digito é 'P'
    else:
        dv = str(11 - resto)
        
    return dv
