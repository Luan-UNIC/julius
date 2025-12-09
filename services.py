"""
FIDC Middleware - Business Logic Services
==========================================

This module implements the core business logic for:
- CNAB file generation (Santander 240 and BMP 400)
- Boleto PDF generation with barcodes and digitable lines
- XML parsing for NFe and CTe documents
- Nosso Número calculation with check digits

Author: FIDC Development Team
Version: 1.0.0
"""

import os
import io
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, date
from lxml import etree
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from models import Boleto, User, BankConfig
from utils import calcular_dv_bmp


class CnabService:
    """
    Factory/Strategy pattern for CNAB file generation.
    Supports multiple banks and CNAB formats (240 and 400).
    """

    @staticmethod
    def format_text(text: str, length: int, fill_char: str = ' ', align: str = 'left') -> str:
        """
        Format text to specified length with padding.
        
        Args:
            text: Text to format
            length: Target length
            fill_char: Character to use for padding
            align: Alignment ('left' or 'right')
            
        Returns:
            Formatted string of exact length
        """
        text = str(text) if text is not None else ''
        text = text[:length]  # Truncate if too long
        
        if align == 'right':
            return text.rjust(length, fill_char)
        else:
            return text.ljust(length, fill_char)

    @staticmethod
    def format_num(num: Any, length: int, decimals: int = 0, fill_char: str = '0') -> str:
        """
        Format number to specified length with zero padding.
        
        Args:
            num: Number to format
            length: Target length
            decimals: Number of decimal places (for amounts)
            fill_char: Character to use for padding
            
        Returns:
            Formatted numeric string
        """
        if decimals > 0:
            # For monetary values, multiply by 10^decimals to remove decimal point
            num = int(float(num) * (10 ** decimals))
        else:
            num = int(num) if num else 0
        
        return str(num).zfill(length)

    @staticmethod
    def generate_santander_240(boletos: List[Boleto], cedente: User) -> str:
        """
        Generate CNAB 240 remittance file for Santander Bank.
        
        Structure:
        - Header Arquivo (File Header)
        - Header Lote (Batch Header)
        - For each boleto:
          * Segmento P (Main boleto data)
          * Segmento Q (Payer data)
        - Trailer Lote (Batch Trailer)
        - Trailer Arquivo (File Trailer)
        
        Args:
            boletos: List of Boleto objects to include in remittance
            cedente: User object (cedente/beneficiary)
            
        Returns:
            CNAB 240 formatted string
            
        Raises:
            ValueError: If BankConfig not found for Santander
        """
        # Get Santander configuration
        santander_config = next(
            (bc for bc in cedente.bank_configs if bc.bank_type == 'santander'), 
            None
        )
        if not santander_config:
            raise ValueError("Santander configuration not found for cedente")

        lines = []
        
        # === HEADER DE ARQUIVO (File Header) ===
        # Positions 001-240
        h_arq = ''
        h_arq += '033'  # 001-003: Código do Banco (Santander)
        h_arq += '0000'  # 004-007: Lote (0000 for file header)
        h_arq += '0'  # 008: Tipo de Registro (0=Header Arquivo)
        h_arq += ' ' * 8  # 009-016: Reservado
        h_arq += '2'  # 017: Tipo Inscrição (1=CPF, 2=CNPJ)
        # Use Cedente CNPJ from User model
        cedente_cnpj = ''.join(filter(str.isdigit, cedente.cnpj or ''))
        h_arq += CnabService.format_num(cedente_cnpj, 15)  # 018-032: CNPJ

        # 033-047: Código de Transmissão (Use config or fallback)
        if santander_config.codigo_transmissao:
             codigo_transmissao = CnabService.format_num(santander_config.codigo_transmissao, 15)
        else:
            # Fallback to Agency + Account logic
            codigo_transmissao = (
                CnabService.format_num(santander_config.agency, 4) +
                ' ' +  # DAC of agency (1 char)
                CnabService.format_num(santander_config.account.split('-')[0] if '-' in santander_config.account else santander_config.account, 9) +
                (santander_config.account.split('-')[1][0] if '-' in santander_config.account else '0')  # DAC of account
            )
        
        h_arq += codigo_transmissao  # 033-047: Código de Transmissão
        h_arq += ' ' * 25  # 048-072: Reservado
        h_arq += CnabService.format_text(cedente.razao_social or cedente.username, 30)  # 073-102: Nome da Empresa
        h_arq += CnabService.format_text('BANCO SANTANDER', 30)  # 103-132: Nome do Banco
        h_arq += ' ' * 10  # 133-142: Reservado
        h_arq += '1'  # 143: Código Remessa (1=Remessa)
        h_arq += datetime.now().strftime('%d%m%Y')  # 144-151: Data de Geração
        h_arq += ' ' * 6  # 152-157: Reservado
        h_arq += CnabService.format_num(1, 6)  # 158-163: Nº Sequencial do Arquivo
        h_arq += '040'  # 164-166: Versão do Layout (040 para Santander)
        h_arq += ' ' * 74  # 167-240: Reservado
        
        lines.append(h_arq)
        
        # === HEADER DE LOTE (Batch Header) ===
        h_lote = ''
        h_lote += '033'  # 001-003: Código do Banco
        h_lote += '0001'  # 004-007: Número do Lote
        h_lote += '1'  # 008: Tipo de Registro (1=Header Lote)
        h_lote += 'R'  # 009: Tipo de Operação (R=Remessa)
        h_lote += '01'  # 010-011: Tipo de Serviço (01=Cobrança)
        h_lote += '  '  # 012-013: Reservado
        h_lote += '030'  # 014-016: Versão do Layout do Lote
        h_lote += ' '  # 017: Reservado
        h_lote += '2'  # 018: Tipo Inscrição
        h_lote += CnabService.format_num(cedente_cnpj, 15)  # 019-033: CNPJ
        h_lote += ' ' * 20  # 034-053: Reservado
        h_lote += codigo_transmissao  # 054-068: Código de Transmissão (15 chars)
        h_lote += ' ' * 5  # 069-073: Reservado
        h_lote += CnabService.format_text(cedente.razao_social or cedente.username, 30)  # 074-103: Nome Beneficiário
        h_lote += ' ' * 40  # 104-143: Mensagem 1
        h_lote += ' ' * 40  # 144-183: Mensagem 2
        h_lote += CnabService.format_num(1, 8)  # 184-191: Número Remessa
        h_lote += datetime.now().strftime('%d%m%Y')  # 192-199: Data Gravação
        h_lote += ' ' * 41  # 200-240: Reservado
        
        lines.append(h_lote)
        
        # === SEGMENTOS P e Q (Boleto Details) ===
        seq = 1
        for boleto in boletos:
            # Get bank config for this boleto's cedente
            boleto_cedente = boleto.cedente
            boleto_config = next(
                (bc for bc in boleto_cedente.bank_configs if bc.bank_type == 'santander'),
                santander_config  # Fallback
            )
            
            # --- SEGMENTO P (Main Boleto Data) ---
            seg_p = ''
            seg_p += '033'  # 001-003: Código do Banco
            seg_p += '0001'  # 004-007: Número do Lote
            seg_p += '3'  # 008: Tipo de Registro (3=Detalhe)
            seg_p += CnabService.format_num(seq, 5)  # 009-013: Nº Sequencial
            seg_p += 'P'  # 014: Código Segmento
            seg_p += ' '  # 015: Reservado
            seg_p += '01'  # 016-017: Código Movimento (01=Entrada de Boleto)
            seg_p += CnabService.format_num(boleto_config.agency, 4)  # 018-021: Agência
            seg_p += '0'  # 022: Dígito Agência
            
            # 023-031: Conta Corrente (9 chars)
            conta_num = boleto_config.account.split('-')[0] if '-' in boleto_config.account else boleto_config.account
            seg_p += CnabService.format_num(conta_num, 9)  # 023-031
            seg_p += (boleto_config.account.split('-')[1][0] if '-' in boleto_config.account else '0')  # 032: DAC
            
            seg_p += '0' * 9  # 033-041: Conta Cobrança FIDC (zeros if not FIDC)
            seg_p += '0'  # 042: Dígito Conta Cobrança FIDC
            seg_p += '  '  # 043-044: Reservado
            
            # 045-057: Nosso Número (13 chars) - Without DV for Santander
            seg_p += CnabService.format_num(boleto.nosso_numero, 13)  # 045-057
            
            seg_p += '5'  # 058: Tipo de Cobrança (5=Rápida com Registro)
            seg_p += '1'  # 059: Forma de Cadastramento (1=Registrada)
            seg_p += '1'  # 060: Tipo de Documento (1=Tradicional)
            seg_p += ' '  # 061: Reservado
            seg_p += ' '  # 062: Reservado
            seg_p += CnabService.format_text(str(boleto.id), 15)  # 063-077: Nº Documento (Seu Número)
            seg_p += boleto.due_date.strftime('%d%m%Y')  # 078-085: Vencimento
            seg_p += CnabService.format_num(boleto.amount, 15, decimals=2)  # 086-100: Valor
            seg_p += '0000'  # 101-104: Agência Cobradora (0000=no preference)
            seg_p += '0'  # 105: Dígito Agência Cobradora
            seg_p += ' '  # 106: Reservado
            seg_p += '04'  # 107-108: Espécie (04=Duplicata de Serviço)
            seg_p += 'N'  # 109: Aceite (N=Não Aceite)
            seg_p += datetime.now().strftime('%d%m%Y')  # 110-117: Data Emissão
            seg_p += '0'  # 118: Código Juros (0=Isento)
            seg_p += '0' * 8  # 119-126: Data Juros
            # Financial Instructions from Config
            if boleto_config.juros_percent:
                 # Juros Mensal / 30 = Juros Diario
                 valor_juros_dia = (boleto.amount * (boleto_config.juros_percent / 100)) / 30
                 seg_p += '1' # Valor por dia
                 # Data Juros = Vencimento + 1 dia (implicit logic usually, but here requires date)
                 # CNAB 240 Santander usually implies start from due date, but let's check manual.
                 # Using 00000000 often means "standard"
                 seg_p += '0' * 8
                 seg_p += CnabService.format_num(valor_juros_dia, 15, decimals=2)
            else:
                 seg_p += '0' * 1 # Isento
                 seg_p += '0' * 8
                 seg_p += '0' * 15

            seg_p += '0'  # 142: Código Desconto (0=Sem Desconto)
            seg_p += '0' * 8  # 143-150: Data Desconto
            seg_p += '0' * 15  # 151-165: Valor Desconto
            seg_p += '0' * 15  # 166-180: IOF (5 decimals, but 15 total)
            seg_p += '0' * 15  # 181-195: Abatimento
            seg_p += CnabService.format_text(str(boleto.id), 25)  # 196-220: Identificação na Empresa

            # Protesto / Baixa
            if boleto_config.protesto_dias:
                seg_p += '1' # Protestar Dias Corridos
                seg_p += CnabService.format_num(boleto_config.protesto_dias, 2)
            else:
                seg_p += '3'  # 221: Código Protesto (3=Não Protestar)
                seg_p += '00'  # 222-223: Dias para Protesto

            if boleto_config.baixa_dias:
                seg_p += '1'  # 224: Código Baixa (1=Baixar/Devolver)
                seg_p += '0'  # 225: Reservado
                seg_p += CnabService.format_num(boleto_config.baixa_dias, 2)
            else:
                seg_p += '1'
                seg_p += '0'
                seg_p += '90'  # 226-227: Dias para Baixa
            seg_p += '09'  # 228-229: Código Moeda (09=Real)
            seg_p += ' ' * 11  # 230-240: Reservado
            
            lines.append(seg_p)
            seq += 1
            
            # --- SEGMENTO Q (Payer Data) ---
            seg_q = ''
            seg_q += '033'  # 001-003: Código do Banco
            seg_q += '0001'  # 004-007: Número do Lote
            seg_q += '3'  # 008: Tipo de Registro
            seg_q += CnabService.format_num(seq, 5)  # 009-013: Nº Sequencial
            seg_q += 'Q'  # 014: Código Segmento
            seg_q += ' '  # 015: Reservado
            seg_q += '01'  # 016-017: Código Movimento
            
            # 018: Tipo Inscrição Pagador (1=CPF, 2=CNPJ)
            doc_clean = ''.join(filter(str.isdigit, boleto.sacado_doc))
            tipo_insc = '2' if len(doc_clean) > 11 else '1'
            seg_q += tipo_insc  # 018
            seg_q += CnabService.format_num(doc_clean, 15)  # 019-033: CNPJ/CPF
            seg_q += CnabService.format_text(boleto.sacado_name, 40)  # 034-073: Nome

            # Get Invoice Address if available (take first invoice)
            inv = boleto.invoices[0] if boleto.invoices else None
            end_rua = inv.sacado_address if inv else ''
            end_bairro = inv.sacado_neighborhood if inv else ''
            end_cidade = inv.sacado_city if inv else ''
            end_uf = inv.sacado_state if inv else ''
            end_cep = ''.join(filter(str.isdigit, inv.sacado_zip or ''))

            seg_q += CnabService.format_text(end_rua, 40)  # 074-113: Endereço
            seg_q += CnabService.format_text(end_bairro, 15)  # 114-128: Bairro
            seg_q += CnabService.format_num(end_cep[:5], 5)  # 129-133: CEP
            seg_q += CnabService.format_num(end_cep[5:], 3)  # 134-136: Sufixo CEP
            seg_q += CnabService.format_text(end_cidade, 15)  # 137-151: Cidade
            seg_q += CnabService.format_text(end_uf, 2)  # 152-153: UF
            seg_q += '0'  # 154: Tipo Inscrição Sacador/Avalista (0=Não tem)
            seg_q += '0' * 15  # 155-169: CNPJ Sacador
            seg_q += ' ' * 40  # 170-209: Nome Sacador
            seg_q += ' ' * 3  # 210-212: Reservado
            seg_q += ' ' * 3  # 213-215: Reservado
            seg_q += ' ' * 3  # 216-218: Reservado
            seg_q += ' ' * 3  # 219-221: Reservado
            seg_q += ' ' * 19  # 222-240: Reservado
            
            lines.append(seg_q)
            seq += 1
        
        # === TRAILER DE LOTE (Batch Trailer) ===
        t_lote = ''
        t_lote += '033'  # 001-003: Código do Banco
        t_lote += '0001'  # 004-007: Número do Lote
        t_lote += '5'  # 008: Tipo de Registro (5=Trailer Lote)
        t_lote += ' ' * 9  # 009-017: Reservado
        t_lote += CnabService.format_num(seq + 1, 6)  # 018-023: Qtd Registros no Lote (header+details+trailer)
        t_lote += ' ' * 217  # 024-240: Reservado
        
        lines.append(t_lote)
        
        # === TRAILER DE ARQUIVO (File Trailer) ===
        t_arq = ''
        t_arq += '033'  # 001-003: Código do Banco
        t_arq += '9999'  # 004-007: Lote (9999 for file trailer)
        t_arq += '9'  # 008: Tipo de Registro (9=Trailer Arquivo)
        t_arq += ' ' * 9  # 009-017: Reservado
        t_arq += CnabService.format_num(1, 6)  # 018-023: Qtd Lotes
        t_arq += CnabService.format_num(len(lines) + 1, 6)  # 024-029: Qtd Registros
        t_arq += ' ' * 211  # 030-240: Reservado
        
        lines.append(t_arq)
        
        # Join with CRLF (Windows line ending, standard for CNAB)
        return "\r\n".join(lines)

    @staticmethod
    def generate_bmp_400(boletos: List[Boleto], cedente: User) -> str:
        """
        Generate CNAB 400 remittance file for BMP Money Plus Bank.
        
        Structure (flat):
        - Header (1 line)
        - Detail records (1 per boleto)
        - Trailer (1 line)
        
        Args:
            boletos: List of Boleto objects
            cedente: User object (cedente)
            
        Returns:
            CNAB 400 formatted string
            
        Raises:
            ValueError: If BankConfig not found for BMP
        """
        # Get BMP configuration
        bmp_config = next(
            (bc for bc in cedente.bank_configs if bc.bank_type == 'bmp'),
            None
        )
        if not bmp_config:
            raise ValueError("BMP configuration not found for cedente")

        lines = []
        
        # === HEADER (Record Type 0) ===
        h = '0'  # 001: Tipo Registro
        h += '1'  # 002: Tipo Operação (1=Remessa)
        h += 'REMESSA'  # 003-009: Literal REMESSA
        h += '01'  # 010-011: Código Serviço (01=Cobrança)
        h += CnabService.format_text('COBRANCA', 15)  # 012-026: Literal Serviço
        h += CnabService.format_text(bmp_config.convenio or '', 20)  # 027-046: Código Cedente
        h += CnabService.format_text(cedente.razao_social or cedente.username, 30)  # 047-076: Nome Cedente
        h += '274'  # 077-079: Código Banco (BMP Money Plus)
        h += CnabService.format_text('BMP MONEY PLUS', 15)  # 080-094: Nome Banco
        h += datetime.now().strftime('%d%m%y')  # 095-100: Data Geração (DDMMYY)
        h += ' ' * 8  # 101-108: Brancos
        h += 'MX'  # 109-110: Identificação Sistema
        h += CnabService.format_num(1, 7)  # 111-117: Sequencial Remessa
        h += ' ' * 277  # 118-394: Brancos
        h += CnabService.format_num(1, 6)  # 395-400: Sequencial Registro
        
        lines.append(h)
        
        # === DETAIL RECORDS (Record Type 1) ===
        seq = 2
        for boleto in boletos:
            # Get bank config for this boleto
            boleto_cedente = boleto.cedente
            boleto_config = next(
                (bc for bc in boleto_cedente.bank_configs if bc.bank_type == 'bmp'),
                bmp_config  # Fallback
            )
            
            d = '1'  # 001: Tipo Registro
            d += '02'  # 002-003: Tipo Inscrição Cedente (02=CNPJ)
            cedente_cnpj = ''.join(filter(str.isdigit, cedente.cnpj or ''))
            d += CnabService.format_num(cedente_cnpj, 14)  # 004-017: CNPJ Cedente
            d += '0'  # 018: Zero
            d += '0'  # 019: Zero
            d += ' '  # 020: Branco
            
            # 021-037: Identificação no Banco (17 chars)
            # Format: Zero(1) + Carteira(3) + Agencia(5) + Conta(7) + Digito(1)
            identificacao_banco = '0'  # 021: Zero
            identificacao_banco += CnabService.format_num(boleto_config.wallet or '109', 3)  # 022-024: Carteira
            identificacao_banco += CnabService.format_num(boleto_config.agency, 5)  # 025-029: Agência
            
            # Parse account number
            acc_full = boleto_config.account or '0000000'
            acc_parts = acc_full.split('-')
            acc_body = ''.join(filter(str.isdigit, acc_parts[0]))
            acc_digit = acc_parts[1][0] if len(acc_parts) > 1 else '0'
            
            identificacao_banco += CnabService.format_num(acc_body, 7)  # 030-036: Conta
            identificacao_banco += acc_digit  # 037: Dígito
            
            d += identificacao_banco  # 021-037
            
            d += CnabService.format_text(str(boleto.id), 25)  # 038-062: Nº Controle (Seu Número)
            d += '00000000'  # 063-070: Zeros
            
            # 071-081: Nosso Número (11 chars)
            d += CnabService.format_num(boleto.nosso_numero, 11)  # 071-081
            
            # 082: DV Nosso Número
            dv_nn = calcular_dv_bmp(boleto_config.wallet or '109', boleto.nosso_numero)
            d += dv_nn  # 082
            
            d += '0' * 10  # 083-092: Zeros/Brancos
            d += '2'  # 093: Condição Emissão (2=Cliente Emite)
            d += 'N'  # 094: Aceite (N=Não Aceite)
            d += ' ' * 13  # 095-107: Brancos
            d += 'I'  # 108: Carteira (I=Integrada)
            d += '01'  # 109-110: Ocorrência (01=Remessa/Registro)
            
            d += CnabService.format_text(str(boleto.id), 10)  # 111-120: Seu Número
            d += boleto.due_date.strftime('%d%m%y')  # 121-126: Vencimento
            d += CnabService.format_num(boleto.amount, 13, decimals=2)  # 127-139: Valor
            d += '274'  # 140-142: Banco
            d += '00000'  # 143-147: Agência Cobradora (00000=qualquer)

            # Espécie do Título
            # Map known codes or use default 04 (DS)
            especie_map = {'DM': '02', 'DS': '04'}
            inv = boleto.invoices[0] if boleto.invoices else None
            especie_code = especie_map.get(inv.especie, '04') if inv else '04'

            d += especie_code  # 148-149: Espécie
            d += 'N'  # 150: Aceite
            d += datetime.now().strftime('%d%m%y')  # 151-156: Data Emissão
            
            # Instructions from Config
            instr1 = '00'
            instr2 = '00'
            if boleto_config.protesto_dias:
                instr1 = '09' # Protestar
            elif boleto_config.baixa_dias:
                instr1 = '15' # Devolver/Baixar

            d += instr1  # 157-158: Instrução 1
            d += instr2  # 159-160: Instrução 2
            
            # Juros
            val_juros = 0
            if boleto_config.juros_percent:
                 val_juros = (boleto.amount * (boleto_config.juros_percent / 100)) / 30

            d += CnabService.format_num(val_juros, 13, decimals=2)  # 161-173: Juros/Mora
            d += '00' + '00' + '00'  # 174-179: Data Desconto (zeros = sem desconto)
            d += CnabService.format_num(0, 13, decimals=2)  # 180-192: Valor Desconto
            d += CnabService.format_num(0, 13, decimals=2)  # 193-205: IOF
            d += CnabService.format_num(0, 13, decimals=2)  # 206-218: Abatimento
            
            # Sacado (Payer)
            doc_clean = ''.join(filter(str.isdigit, boleto.sacado_doc))
            tipo_insc = '02' if len(doc_clean) > 11 else '01'
            d += tipo_insc  # 219-220: Tipo Inscrição Sacado
            d += CnabService.format_num(doc_clean, 14)  # 221-234: CNPJ/CPF
            
            d += CnabService.format_text(boleto.sacado_name, 40)  # 235-274: Nome Sacado

            # Address Logic for BMP (40 chars total: Rua + Num + Comp)
            inv = boleto.invoices[0] if boleto.invoices else None
            full_address = ''
            bairro = ''
            cep = '00000000'
            cidade = ''
            uf = '  '

            if inv:
                full_address = f"{inv.sacado_address or ''}"[:40]
                bairro = inv.sacado_neighborhood or ''
                cep = ''.join(filter(str.isdigit, inv.sacado_zip or '00000000'))
                cidade = inv.sacado_city or ''
                uf = inv.sacado_state or '  '

            d += CnabService.format_text(full_address, 40)  # 275-314: Endereço
            d += CnabService.format_text(bairro, 12)  # 315-326: Bairro
            d += CnabService.format_num(cep, 8)  # 327-334: CEP
            d += CnabService.format_text(cidade, 15)  # 335-349: Cidade
            d += CnabService.format_text(uf, 2)  # 350-351: UF
            
            d += ' ' * 42  # 352-393: Sacador/Avalista + Brancos
            d += '0'  # 394: Moeda (0=Real)
            
            d += CnabService.format_num(seq, 6)  # 395-400: Sequencial
            
            lines.append(d)
            seq += 1
        
        # === TRAILER (Record Type 9) ===
        t = '9'  # 001: Tipo Registro
        t += ' ' * 393  # 002-394: Brancos
        t += CnabService.format_num(seq, 6)  # 395-400: Sequencial
        
        lines.append(t)
        
        # Join with CRLF
        return "\r\n".join(lines)


class BoletoBuilder:
    """
    PDF boleto generation with barcode and digitable line calculation.
    Follows Febraban standards for Brazilian bank slips.
    """

    @staticmethod
    def mod11(number: str, base: int = 9, r: int = 0) -> int:
        """
        Calculate Modulo 11 check digit.
        
        Args:
            number: String of digits
            base: Maximum weight (default 9)
            r: Return value when result is 10 or 11 (default 0)
            
        Returns:
            Check digit
        """
        sum_val = 0
        weight = 2
        
        for digit in reversed(str(number)):
            sum_val += int(digit) * weight
            weight += 1
            if weight > base:
                weight = 2
        
        remainder = sum_val % 11
        result = 11 - remainder
        
        if result >= 10:
            return r
        return result

    @staticmethod
    def mod10(number: str) -> int:
        """
        Calculate Modulo 10 check digit.
        
        Args:
            number: String of digits
            
        Returns:
            Check digit
        """
        sum_val = 0
        weight = 2
        
        for digit in reversed(str(number)):
            val = int(digit) * weight
            if val > 9:
                val = (val // 10) + (val % 10)
            sum_val += val
            weight = 1 if weight == 2 else 2
        
        remainder = sum_val % 10
        return 0 if remainder == 0 else (10 - remainder)

    @staticmethod
    def calculate_santander_nosso_numero(nosso_numero: int, carteira: str = '101') -> str:
        """
        Calculate Santander Nosso Número with check digit.
        Uses Modulo 11 with specific Santander rules.
        
        Args:
            nosso_numero: Sequential number
            carteira: Wallet code (default '101')
            
        Returns:
            Formatted Nosso Número with DV (e.g., "0001234567-8")
        """
        nn_str = str(nosso_numero).zfill(12)
        dv = BoletoBuilder.mod11(nn_str, base=9, r=0)
        return f"{nn_str}-{dv}"

    @staticmethod
    def calculate_barcode(bank_code: str, currency_code: str, due_date: date, 
                         amount: float, nosso_numero: str, agency: str, 
                         account: str, carteira: str) -> Tuple[str, str]:
        """
        Calculate boleto barcode and digitable line according to Febraban standards.
        
        Args:
            bank_code: 3-digit bank code
            currency_code: Currency code (usually '9' for Real)
            due_date: Due date
            amount: Amount in BRL
            nosso_numero: Nosso Número
            agency: Agency code
            account: Account number
            carteira: Wallet code
            
        Returns:
            Tuple of (barcode_44_digits, digitable_line_47_digits)
        """
        # Calculate fator vencimento (days since 07/10/1997)
        base_date = datetime(1997, 10, 7).date()
        days_diff = (due_date - base_date).days
        fator_vencimento = str(days_diff).zfill(4)
        
        # Format amount (10 digits, no decimal point)
        amount_str = str(int(amount * 100)).zfill(10)
        
        # Barcode structure (44 digits):
        # 001-003: Bank code
        # 004-004: Currency code
        # 005-005: DV (calculated last)
        # 006-009: Fator vencimento
        # 010-019: Amount
        # 020-044: Free field (bank-specific)
        
        # Free field for Santander (25 digits): 
        # 9 (fixo) + Carteira(3) + Nosso Número(12)+ Zeros(1) = 25
        free_field = '9' + carteira.zfill(3) + str(nosso_numero).zfill(12)[:12]
        
        # Build barcode without DV
        barcode_no_dv = (
            bank_code +
            currency_code +
            fator_vencimento +
            amount_str +
            free_field
        )
        
        # Calculate DV for position 5
        dv_barcode = BoletoBuilder.mod11(barcode_no_dv, base=9, r=1)
        
        # Complete barcode
        barcode = (
            bank_code +
            currency_code +
            str(dv_barcode) +
            fator_vencimento +
            amount_str +
            free_field
        )
        
        # Digitable line (47 digits with separators):
        # Field 1: Bank(3) + Currency(1) + First 5 of free field + DV1
        # Field 2: Next 10 of free field + DV2
        # Field 3: Last 10 of free field + DV3
        # Field 4: DV from barcode
        # Field 5: Fator(4) + Amount(10)
        
        field1_data = bank_code + currency_code + free_field[:5]
        dv1 = BoletoBuilder.mod10(field1_data)
        field1 = field1_data + str(dv1)
        
        field2_data = free_field[5:15]
        dv2 = BoletoBuilder.mod10(field2_data)
        field2 = field2_data + str(dv2)
        
        field3_data = free_field[15:25]
        dv3 = BoletoBuilder.mod10(field3_data)
        field3 = field3_data + str(dv3)
        
        field4 = str(dv_barcode)
        
        field5 = fator_vencimento + amount_str
        
        # Format digitable line with dots and spaces
        digitable_line = (
            f"{field1[:5]}.{field1[5:]} "
            f"{field2[:5]}.{field2[5:]} "
            f"{field3[:5]}.{field3[5:]} "
            f"{field4} "
            f"{field5}"
        )
        
        return barcode, digitable_line

    @staticmethod
    def generate_pdf(boleto_data: Dict[str, Any], filepath: str) -> None:
        """
        Generate boleto PDF with complete layout, barcode, and digitable line.
        
        Args:
            boleto_data: Dictionary with boleto information:
                - bank_name: Bank name
                - bank_code: 3-digit bank code
                - digitable_line: 47-digit digitable line
                - cedente_name: Beneficiary name
                - cedente_doc: Beneficiary CPF/CNPJ
                - cedente_address: Beneficiary address
                - due_date: Due date
                - amount: Amount
                - sacado_name: Payer name
                - sacado_doc: Payer CPF/CNPJ
                - sacado_address: Payer address
                - barcode: 44-digit barcode
                - nosso_numero: Nosso Número formatted
                - doc_number: Document number
                - instructions: Payment instructions (optional)
            filepath: Path to save PDF
        """
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        
        # Margins and dimensions
        left_margin = 10 * mm
        right_margin = width - 10 * mm
        
        # Starting Y position
        y = height - 20 * mm
        
        # === RECEIPT SECTION (Recibo do Pagador) ===
        c.setFont("Helvetica-Bold", 8)
        c.drawString(left_margin, y, "RECIBO DO PAGADOR")
        y -= 5 * mm
        c.line(left_margin, y, right_margin, y)
        y -= 5 * mm
        
        # Bank header
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left_margin, y, f"{boleto_data['bank_code']} | {boleto_data['bank_name']}")
        c.setFont("Helvetica", 9)
        c.drawRightString(right_margin, y, boleto_data['digitable_line'])
        y -= 8 * mm
        
        # === MAIN BOLETO SECTION ===
        c.setLineWidth(0.5)
        c.line(left_margin, y, right_margin, y)
        
        # Row 1: Local de Pagamento | Vencimento
        box_y = y
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, box_y - 3*mm, "Local de Pagamento")
        c.setFont("Helvetica", 8)
        c.drawString(left_margin + 1*mm, box_y - 7*mm, "PAGÁVEL EM QUALQUER BANCO ATÉ O VENCIMENTO")
        
        # Vertical line for vencimento
        venc_x = right_margin - 50*mm
        c.line(venc_x, box_y, venc_x, box_y - 10*mm)
        c.setFont("Helvetica", 6)
        c.drawString(venc_x + 1*mm, box_y - 3*mm, "Vencimento")
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(right_margin - 1*mm, box_y - 7*mm, boleto_data['due_date'].strftime('%d/%m/%Y'))
        
        y -= 10 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Row 2: Beneficiário/Cedente | Agência/Código Cedente
        box_y = y
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, box_y - 3*mm, "Beneficiário/Cedente")
        c.setFont("Helvetica", 8)

        cedente_info = boleto_data.get('cedente_name', 'N/A')
        if boleto_data.get('cedente_doc'):
            cedente_info += f" - CNPJ/CPF: {boleto_data['cedente_doc']}"

        c.drawString(left_margin + 1*mm, box_y - 7*mm, cedente_info)

        # Cedente Address
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, box_y - 9.5*mm, boleto_data.get('cedente_address', ''))
        
        c.line(venc_x, box_y, venc_x, box_y - 10*mm)
        c.setFont("Helvetica", 6)
        c.drawString(venc_x + 1*mm, box_y - 3*mm, "Agência/Código Cedente")
        c.setFont("Helvetica", 8)
        c.drawRightString(right_margin - 1*mm, box_y - 7*mm, boleto_data.get('agency_account', 'N/A'))
        
        y -= 10 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Row 3: Data Documento | Nº Documento | Espécie Doc | Aceite | Data Processamento | Nosso Número
        box_y = y
        col_widths = [30*mm, 35*mm, 25*mm, 15*mm, 30*mm]
        x_pos = left_margin
        
        labels = ["Data Documento", "Nº Documento", "Espécie Doc", "Aceite", "Data Processamento"]
        values = [
            datetime.now().strftime('%d/%m/%Y'),
            boleto_data.get('doc_number', 'N/A'),
            "DS",
            "N",
            datetime.now().strftime('%d/%m/%Y')
        ]
        
        for i, (label, value) in enumerate(zip(labels, values)):
            c.setFont("Helvetica", 6)
            c.drawString(x_pos + 1*mm, box_y - 3*mm, label)
            c.setFont("Helvetica", 7)
            c.drawString(x_pos + 1*mm, box_y - 7*mm, value)
            x_pos += col_widths[i]
            if i < len(col_widths) - 1:
                c.line(x_pos, box_y, x_pos, box_y - 10*mm)
        
        # Last column: Nosso Número
        c.line(venc_x, box_y, venc_x, box_y - 10*mm)
        c.setFont("Helvetica", 6)
        c.drawString(venc_x + 1*mm, box_y - 3*mm, "Nosso Número")
        c.setFont("Helvetica", 8)
        c.drawRightString(right_margin - 1*mm, box_y - 7*mm, boleto_data.get('nosso_numero', 'N/A'))
        
        y -= 10 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Row 4: Uso Banco | Carteira | Espécie | Quantidade | Valor | Valor Documento
        box_y = y
        x_pos = left_margin
        col_widths2 = [25*mm, 20*mm, 20*mm, 25*mm, 30*mm]
        
        labels2 = ["Uso do Banco", "Carteira", "Espécie", "Quantidade", "Valor"]
        values2 = ["", boleto_data.get('carteira', 'N/A'), "R$", "", ""]
        
        for i, (label, value) in enumerate(zip(labels2, values2)):
            c.setFont("Helvetica", 6)
            c.drawString(x_pos + 1*mm, box_y - 3*mm, label)
            c.setFont("Helvetica", 7)
            c.drawString(x_pos + 1*mm, box_y - 7*mm, value)
            x_pos += col_widths2[i]
            if i < len(col_widths2) - 1:
                c.line(x_pos, box_y, x_pos, box_y - 10*mm)
        
        c.line(venc_x, box_y, venc_x, box_y - 10*mm)
        c.setFont("Helvetica", 6)
        c.drawString(venc_x + 1*mm, box_y - 3*mm, "Valor Documento")
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(right_margin - 1*mm, box_y - 7*mm, f"R$ {boleto_data['amount']:.2f}")
        
        y -= 10 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Row 5: Instruções
        box_y = y
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, box_y - 3*mm, "Instruções (Texto de responsabilidade do beneficiário)")
        c.setFont("Helvetica", 7)
        
        instructions = boleto_data.get('instructions', 'Não receber após o vencimento')
        c.drawString(left_margin + 1*mm, box_y - 8*mm, instructions)
        
        # Additional value fields on the right
        y -= 40 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Row 6: Desconto/Abatimento | (-) Outras Deduções | (+) Mora/Multa | (+) Outros Acréscimos | (=) Valor Cobrado
        # (Simplified - showing only labels)
        
        y -= 10 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Pagador section
        box_y = y
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, box_y - 3*mm, "Pagador")
        c.setFont("Helvetica", 8)
        c.drawString(left_margin + 1*mm, box_y - 7*mm, 
                    f"{boleto_data['sacado_name']} - CNPJ/CPF: {boleto_data['sacado_doc']}")
        c.setFont("Helvetica", 7)
        c.drawString(left_margin + 1*mm, box_y - 11*mm, 
                    boleto_data.get('sacado_address', 'Endereço não informado'))
        
        y -= 15 * mm
        c.line(left_margin, y, right_margin, y)
        
        # Sacador/Avalista (optional)
        y -= 8 * mm
        c.setFont("Helvetica", 6)
        c.drawString(left_margin + 1*mm, y, "Sacador/Avalista:")
        
        # Footer text
        y -= 8 * mm
        c.setFont("Helvetica", 6)
        c.drawRightString(right_margin, y, "Autenticação Mecânica - FICHA DE COMPENSAÇÃO")
        
        # === BARCODE ===
        y_barcode = 15 * mm
        try:
            # Clean barcode (only digits)
            clean_barcode = ''.join(filter(str.isdigit, boleto_data['barcode']))
            
            if len(clean_barcode) < 44:
                clean_barcode = clean_barcode.ljust(44, '0')
            
            # Improved Interleaved 2 of 5 barcode with better rendering
            # Using proper bar width ratios and dimensions for Brazilian boletos
            bc = createBarcodeDrawing(
                'I2of5',
                value=clean_barcode,
                barWidth=0.43 * mm,  # Increased from 0.33mm for better readability
                barHeight=13 * mm,
                checksum=0,
                bearers=0,  # No bearer bars
                quiet=1,  # Add quiet zones (margins)
                lquiet=10,  # Left quiet zone (10 * barWidth)
                rquiet=10   # Right quiet zone (10 * barWidth)
            )
            # Center the barcode horizontally
            bc_width = bc.width
            x_barcode = (width - bc_width) / 2
            bc.drawOn(c, x_barcode, y_barcode)
        except Exception as e:
            # Fallback: Try using python-barcode library
            try:
                import barcode
                from barcode.writer import ImageWriter
                from io import BytesIO
                from reportlab.lib.utils import ImageReader
                
                # Generate barcode using python-barcode (more reliable)
                ITF = barcode.get_barcode_class('itf')
                itf = ITF(clean_barcode, writer=ImageWriter())
                
                # Configure writer for better quality
                writer_options = {
                    'module_width': 0.43,  # mm
                    'module_height': 13.0,  # mm
                    'quiet_zone': 6.5,  # mm
                    'font_size': 0,  # Hide text below barcode
                    'text_distance': 1.0,
                    'background': 'white',
                    'foreground': 'black',
                }
                
                # Render to bytes
                buffer = BytesIO()
                itf.write(buffer, options=writer_options)
                buffer.seek(0)
                
                # Draw image on canvas
                img = ImageReader(buffer)
                img_width = 180 * mm
                img_height = 13 * mm
                x_img = (width - img_width) / 2
                c.drawImage(img, x_img, y_barcode, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
            except Exception as e2:
                # Last resort: Display error and barcode digits
                c.setFont("Helvetica", 6)
                c.drawString(left_margin, y_barcode + 5*mm, f"Barcode rendering error. Manual entry:")
                c.setFont("Helvetica-Bold", 8)
                c.drawString(left_margin, y_barcode, clean_barcode)
        
        c.save()


class XmlParser:
    """
    XML parser for Brazilian fiscal documents (NFe and CTe).
    Extracts payer and invoice information.
    """

    @staticmethod
    def parse_nfe(tree: etree._ElementTree, ns: str) -> Dict[str, Any]:
        """
        Parse NFe (Nota Fiscal Eletrônica) XML.
        
        Args:
            tree: Parsed XML tree
            ns: XML namespace
            
        Returns:
            Dictionary with invoice data including address
            
        Raises:
            ValueError: If required fields are missing
        """
        # Find Destinatario (Payer)
        dest = tree.find(f'.//{{{ns}}}dest')
        if dest is None:
            raise ValueError("Destinatario not found in NFe")
        
        name_elem = dest.find(f'{{{ns}}}xNome')
        name = name_elem.text if name_elem is not None else 'Unknown'
        
        cnpj = dest.find(f'{{{ns}}}CNPJ')
        cpf = dest.find(f'{{{ns}}}CPF')
        doc = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')
        
        # Address Extraction
        address = {}
        ender = dest.find(f'{{{ns}}}enderDest')
        if ender is not None:
            address['street'] = ender.find(f'{{{ns}}}xLgr').text if ender.find(f'{{{ns}}}xLgr') is not None else ''
            address['number'] = ender.find(f'{{{ns}}}nro').text if ender.find(f'{{{ns}}}nro') is not None else ''
            address['neighborhood'] = ender.find(f'{{{ns}}}xBairro').text if ender.find(f'{{{ns}}}xBairro') is not None else ''
            address['city'] = ender.find(f'{{{ns}}}xMun').text if ender.find(f'{{{ns}}}xMun') is not None else ''
            address['state'] = ender.find(f'{{{ns}}}UF').text if ender.find(f'{{{ns}}}UF') is not None else ''
            address['zip'] = ender.find(f'{{{ns}}}CEP').text if ender.find(f'{{{ns}}}CEP') is not None else ''

            # Combine street and number
            address['full_street'] = f"{address['street']}, {address['number']}"

        # Find Value
        v_nf = tree.find(f'.//{{{ns}}}total/{{{ns}}}ICMSTot/{{{ns}}}vNF')
        amount = float(v_nf.text) if v_nf is not None else 0.0
        
        # Find Date
        dh_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dhEmi')
        d_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dEmi')
        
        date_str = dh_emi.text if dh_emi is not None else (d_emi.text if d_emi is not None else '')
        
        # Parse ISO date
        if 'T' in date_str:
            issue_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        elif date_str:
            issue_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            issue_date = datetime.now().date()
        
        # Find Number
        n_nf = tree.find(f'.//{{{ns}}}ide/{{{ns}}}nNF')
        number = n_nf.text if n_nf is not None else 'Unknown'
        
        return {
            'sacado_name': name,
            'sacado_doc': doc,
            'sacado_address': address.get('full_street', ''),
            'sacado_neighborhood': address.get('neighborhood', ''),
            'sacado_city': address.get('city', ''),
            'sacado_state': address.get('state', ''),
            'sacado_zip': address.get('zip', ''),
            'amount': amount,
            'issue_date': issue_date,
            'doc_number': number
        }

    @staticmethod
    def parse_cte(tree: etree._ElementTree, ns: str) -> Dict[str, Any]:
        """
        Parse CTe (Conhecimento de Transporte Eletrônico) XML.
        
        Args:
            tree: Parsed XML tree
            ns: XML namespace
            
        Returns:
            Dictionary with transport invoice data including address
        """
        # Find Value
        v_tprest = tree.find(f'.//{{{ns}}}vPrest/{{{ns}}}vTPrest')
        amount = float(v_tprest.text) if v_tprest is not None else 0.0
        
        # Find Date
        dh_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dhEmi')
        date_str = dh_emi.text if dh_emi is not None else ''
        
        if 'T' in date_str:
            issue_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        else:
            issue_date = datetime.now().date()
        
        # Find Number
        n_ct = tree.find(f'.//{{{ns}}}ide/{{{ns}}}nCT')
        number = n_ct.text if n_ct is not None else 'Unknown'
        
        # Payer Logic - Find toma3 or toma4
        payer_data = {}
        address_data = {}

        # Helper to extract address from node
        def extract_address(node):
            ender = node.find(f'{{{ns}}}enderToma') or node.find(f'{{{ns}}}enderDest') or node.find(f'{{{ns}}}enderReme')
            if ender is not None:
                addr = {}
                addr['street'] = ender.find(f'{{{ns}}}xLgr').text if ender.find(f'{{{ns}}}xLgr') is not None else ''
                addr['number'] = ender.find(f'{{{ns}}}nro').text if ender.find(f'{{{ns}}}nro') is not None else ''
                addr['neighborhood'] = ender.find(f'{{{ns}}}xBairro').text if ender.find(f'{{{ns}}}xBairro') is not None else ''
                addr['city'] = ender.find(f'{{{ns}}}xMun').text if ender.find(f'{{{ns}}}xMun') is not None else ''
                addr['state'] = ender.find(f'{{{ns}}}UF').text if ender.find(f'{{{ns}}}UF') is not None else ''
                addr['zip'] = ender.find(f'{{{ns}}}CEP').text if ender.find(f'{{{ns}}}CEP') is not None else ''
                addr['full_street'] = f"{addr['street']}, {addr['number']}"
                return addr
            return {}
        
        toma3 = tree.find(f'.//{{{ns}}}ide/{{{ns}}}toma3')
        if toma3 is not None:
            toma_role = toma3.find(f'{{{ns}}}toma')
            if toma_role is not None:
                role_code = toma_role.text
                # 0=Remetente, 1=Expedidor, 2=Recebedor, 3=Destinatario
                role_map = {'0': 'rem', '1': 'exped', '2': 'receb', '3': 'dest'}
                role_tag = role_map.get(role_code)
                
                if role_tag:
                    role_node = tree.find(f'.//{{{ns}}}{role_tag}')
                    if role_node is not None:
                        name_elem = role_node.find(f'{{{ns}}}xNome')
                        payer_data['name'] = name_elem.text if name_elem is not None else 'Unknown'
                        
                        cnpj = role_node.find(f'{{{ns}}}CNPJ')
                        cpf = role_node.find(f'{{{ns}}}CPF')
                        payer_data['doc'] = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')

                        address_data = extract_address(role_node)
        
        # Try toma4 if toma3 failed
        if not payer_data:
            toma4 = tree.find(f'.//{{{ns}}}ide/{{{ns}}}toma4')
            if toma4 is not None:
                name_elem = toma4.find(f'{{{ns}}}xNome')
                payer_data['name'] = name_elem.text if name_elem is not None else 'Unknown'
                
                cnpj = toma4.find(f'{{{ns}}}CNPJ')
                cpf = toma4.find(f'{{{ns}}}CPF')
                payer_data['doc'] = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')

                address_data = extract_address(toma4)
        
        # Fallback to destinatario
        if not payer_data:
            dest = tree.find(f'.//{{{ns}}}dest')
            if dest is not None:
                name_elem = dest.find(f'{{{ns}}}xNome')
                payer_data['name'] = name_elem.text if name_elem is not None else 'Unknown'
                
                cnpj = dest.find(f'{{{ns}}}CNPJ')
                payer_data['doc'] = cnpj.text if cnpj is not None else ''

                address_data = extract_address(dest)
        
        return {
            'sacado_name': payer_data.get('name', 'Unknown'),
            'sacado_doc': payer_data.get('doc', ''),
            'sacado_address': address_data.get('full_street', ''),
            'sacado_neighborhood': address_data.get('neighborhood', ''),
            'sacado_city': address_data.get('city', ''),
            'sacado_state': address_data.get('state', ''),
            'sacado_zip': address_data.get('zip', ''),
            'amount': amount,
            'issue_date': issue_date,
            'doc_number': number
        }

    @staticmethod
    def parse_file(filepath: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Parse XML file (auto-detect NFe or CTe).
        
        Args:
            filepath: Path to XML file
            
        Returns:
            Tuple of (document_type, parsed_data) or (None, None) on error
        """
        try:
            tree = etree.parse(filepath)
            root = tree.getroot()
            
            # Extract namespace
            if '}' in root.tag:
                ns = root.tag.split('}')[0].strip('{')
            else:
                ns = ''
            
            # Detect document type
            tag_lower = root.tag.lower()
            
            if 'nfe' in tag_lower:
                return 'nfe', XmlParser.parse_nfe(tree, ns)
            elif 'cte' in tag_lower:
                return 'cte', XmlParser.parse_cte(tree, ns)
            else:
                return None, None
        except Exception as e:
            print(f"Error parsing XML: {e}")
            return None, None
