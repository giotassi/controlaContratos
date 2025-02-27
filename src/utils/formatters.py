import logging

def format_cnpj(cnpj: str) -> str:
    """
    Formata um CNPJ, removendo caracteres não numéricos
    Exemplo: '12.345.678/0001-90' -> '12345678000190'
    """
    try:
        formatted = ''.join(filter(str.isdigit, cnpj))
        logging.info(f"CNPJ formatado: {formatted}")
        return formatted
    except Exception as e:
        logging.error(f"Erro ao formatar CNPJ: {str(e)}")
        return cnpj

def validate_cnpj(cnpj: str) -> bool:
    """
    Valida um CNPJ verificando:
    - Se tem 14 dígitos após remover caracteres não numéricos
    - Se todos os dígitos não são iguais
    - Se os dígitos verificadores estão corretos
    """
    try:
        # Remove caracteres não numéricos
        cnpj = format_cnpj(cnpj)
        logging.info(f"Validando CNPJ: {cnpj}")
        
        # Verifica se tem 14 dígitos
        if len(cnpj) != 14:
            logging.warning(f"CNPJ com tamanho inválido: {len(cnpj)} dígitos")
            return False
            
        # Verifica se todos os dígitos são iguais
        if len(set(cnpj)) == 1:
            logging.warning("CNPJ com todos os dígitos iguais")
            return False
            
        # Primeiro dígito verificador
        multiplicadores1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = 0
        for i in range(12):
            soma += int(cnpj[i]) * multiplicadores1[i]
        
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto
        
        # Segundo dígito verificador
        multiplicadores2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        soma = 0
        for i in range(13):
            soma += int(cnpj[i]) * multiplicadores2[i]
        
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto
        
        # Verifica os dígitos calculados com os dígitos informados
        is_valid = int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2
        logging.info(f"CNPJ válido: {is_valid} (dígitos esperados: {digito1}{digito2}, recebidos: {cnpj[12]}{cnpj[13]})")
        return is_valid
        
    except Exception as e:
        logging.error(f"Erro ao validar CNPJ: {str(e)}")
        return False 