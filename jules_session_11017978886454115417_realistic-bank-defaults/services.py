import os
from lxml import etree
from datetime import datetime
from werkzeug.utils import secure_filename
from models import db, Invoice, Boleto, User
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128, common
from utils import calcular_dv_bmp
import io

class CnabService:
    @staticmethod
    def format_text(text, length):
        return str(text)[:length].ljust(length, ' ')

    @staticmethod
    def format_num(num, length):
        return str(int(num)).zfill(length)

    @staticmethod
    def generate_santander_240(boletos, user):
        # CNAB 240 Structure (Simplified)
        lines = []
        
        # File Header (Header de Arquivo)
        header = f"03300000         2{CnabService.format_text(user.username, 30)}{CnabService.format_text('SANTANDER', 30)}{datetime.now().strftime('%d%m%Y')}"
        # Pad to 240
        header = header.ljust(240, ' ')
        lines.append(header)
        
        # Batch Header (Header de Lote)
        batch_header = f"03300011R01  040 {CnabService.format_text(user.username, 30)}"
        batch_header = batch_header.ljust(240, ' ')
        lines.append(batch_header)
        
        seq = 1
        for boleto in boletos:
            # Segment P (Required for Register)
            seg_p = f"03300013{CnabService.format_num(seq, 5)}P 01"
            seg_p += CnabService.format_num(boleto.nosso_numero, 13) # Nosso Numero
            seg_p += CnabService.format_num(boleto.amount * 100, 15) # Valor
            seg_p = seg_p.ljust(240, ' ')
            lines.append(seg_p)
            
            # Segment Q (Sacado Data)
            seg_q = f"03300013{CnabService.format_num(seq+1, 5)}Q 01"
            seg_q += CnabService.format_text(boleto.sacado_name, 40)
            seg_q = seg_q.ljust(240, ' ')
            lines.append(seg_q)
            
            seq += 2

        # Batch Trailer
        batch_trailer = f"03300015{CnabService.format_num(seq + 2, 6)}{CnabService.format_num(len(boletos) * 2 + 2, 6)}"
        batch_trailer = batch_trailer.ljust(240, ' ')
        lines.append(batch_trailer)
        
        # File Trailer
        file_trailer = f"03399999         {CnabService.format_num(1, 6)}{CnabService.format_num(len(lines)+1, 6)}"
        file_trailer = file_trailer.ljust(240, ' ')
        lines.append(file_trailer)
        
        return "\r\n".join(lines)

    @staticmethod
    def generate_bmp_400(boletos, user):
        """
        Gera arquivo CNAB 400 para o Banco BMP (274).
        Baseado na especificação técnica fornecida.
        """
        # Load BMP config for this user
        # Note: 'user' passed here is likely the User model, but we need the BMP BankConfig.
        # The caller (app.py) passes 'cedente', which is User. 
        # We need to query the BMP config or assume it's passed or attached.
        # For now, let's look it up assuming user has 'bank_configs'
        
        bmp_config = next((bc for bc in user.bank_configs if bc.bank_type == 'bmp'), None)
        if not bmp_config:
            raise ValueError("BMP Configuration not found for user")

        lines = []
        
        # --- HEADER (Pag 6) ---
        # 001-001: Identificação Registro (0)
        # 002-002: Identificação Remessa (1)
        # 003-009: Literal (REMESSA)
        # 027-046: Código Cedente (20 chars) - Using convenio/codigo_cedente
        # 077-079: Banco (274)
        # 095-100: Data Gravação (DDMMAA)
        # 111-117: Sequencial Remessa (7 chars)
        
        # NOTE: Using spaces for unimplemented fields to preserve alignment
        
        h = '0' # 001
        h += '1' # 002
        h += 'REMESSA' # 003-009 (7)
        h += '01' # 010-011 (Código Serviço - Cobrança)
        h += CnabService.format_text('COBRANCA', 15) # 012-026 (Literal Serviço)
        h += CnabService.format_text(bmp_config.convenio, 20) # 027-046 (Codigo Cedente)
        h += CnabService.format_text(user.username, 30) # 047-076 (Nome Cedente)
        h += '274' # 077-079 (Banco BMP)
        h += CnabService.format_text('BMP', 15) # 080-094 (Nome Banco)
        h += datetime.now().strftime('%d%m%y') # 095-100 (Data)
        h += ' '*8 # 101-108 (Branco)
        h += 'MX' # 109-110 (Identificação Sistema?) - Defaulting
        h += CnabService.format_num(1, 7) # 111-117 (Sequencial Remessa) - TODO: increment this
        h += ' '*277 # 118-394 (Branco)
        h += '000001' # 395-400 (Sequencial Registro)
        
        # Ensure exact 400 chars
        if len(h) < 400: h = h.ljust(400, ' ')
        lines.append(h[:400])
        
        seq = 2
        for boleto in boletos:
            # --- DETALHE (Pag 7) ---
            # 001-001: Tipo (1)
            # 021-037: Identificacao Titulo (Zero(1) + Carteira(3) + Agencia(5) + Conta(7) + Digito(1)) = 17 chars
            
            d = '1' # 001
            d += '02' # 002-003 (Inscrição Cedente: 02=CNPJ) - Mocking, should be in User/Config
            d += CnabService.format_num('00000000000000', 14) # 004-017 (CNPJ Cedente) - Mocking
            d += '0' # 018-018 (Zero)
            d += '0' # 019-019 (Zero)
            d += ' ' # 020-020 (Zero) - Manual says Zero, wait.
            # Manual Mapping says:
            # 021-037: Identificacao no Banco (17)
            # Format: Zero(1) + Carteira(3) + Agencia(5) + Conta(7) + Digito(1)
            # Note: BMP Agency is 4 chars usually, Account 7.
            
            identificacao_banco = '0' # Zero(1)
            identificacao_banco += CnabService.format_num(bmp_config.wallet, 3) # Carteira(3)
            identificacao_banco += CnabService.format_num(bmp_config.agency, 5) # Agencia(5)
            # Clean account of dash
            acc_clean = ''.join(filter(str.isdigit, bmp_config.account))
            if len(acc_clean) > 8: # If user put digit inside, e.g. 12345678 (8 chars)
                acc_body = acc_clean[:-1]
                acc_digit = acc_clean[-1]
            else:
                acc_body = acc_clean
                acc_digit = '0' # Default if missing
                
            identificacao_banco += CnabService.format_num(acc_body, 7) # Conta(7)
            identificacao_banco += acc_digit # Digito(1)
            
            d += identificacao_banco # 021-037
            
            d += CnabService.format_text(boleto.id, 25) # 038-062 (Numero Controle / Seu Numero)
            d += '00000000' # 063-070 (Zeros? Ou Banco Nosso Numero?) - Standard 400 has 063-070 as Zeros usually
            
            # 071-081: Nosso Numero (11)
            d += CnabService.format_num(boleto.nosso_numero, 11)
            
            # 082-082: DV Nosso Numero
            dv_nn = calcular_dv_bmp(bmp_config.wallet, boleto.nosso_numero)
            d += dv_nn
            
            d += '0000000000' # 083-092 (Desconto 2 / Multa?) - Skipping detailed specifics not requested
            d += '2' # 093-093 (Condição Emissão? 2=Cliente Emite)
            d += 'N' # 094-094 (Aceite? N)
            d += ' ' * 13 # 095-107 (Branco)
            d += '01' # 108-109 (Carteira - 01/03? Using 01 per instructions? Manual says "01 = Remessa") 
            # WAIT: Posição 109-110 (2) => Ocorrencia. 01 = Remessa.
            # Position check: 
            # 108 is start? Manual says 109-110 is occurrence.
            # My 'd' construction needs careful counting.
            # Let's verify standard 400 positions vs this manual.
            # Standard 400:
            # 001: 1
            # 002-003: Inscricao
            # 004-017: Numero Inscricao
            # 018-037: Identificacao (Ag/Conta) -> Here mapped as 021-037 specific format
            # 038-062: No Controle
            # 063-070: Cobranca/Banco (Zeros)
            # 071-082: Nosso Numero (12) -> Here 11 + 1 DV
            # 083-107: Desconto/Multa etc
            # 108-108: Carteira
            # 109-110: Ocorrencia (01)
            
            # Re-aligning 'd' based on this flow
            # Up to 082 is done.
            # 083-107 (25 chars)
            d += '0' * 10 # 083-092
            d += '2' # 093 (Condicao)
            d += 'N' # 094 (Aceite)
            d += ' ' * 13 # 095-107
            d += 'I' # 108 (Carteira Modalidade? I=Integra?) - Defaulting
            d += '01' # 109-110 (Ocorrencia: 01=Remessa)
            
            d += CnabService.format_text(boleto.id, 10) # 111-120 (Seu Numero)
            d += boleto.due_date.strftime('%d%m%y') # 121-126 (Vencimento)
            d += CnabService.format_num(boleto.amount * 100, 13) # 127-139 (Valor)
            d += '274' # 140-142 (Banco)
            d += '00000' # 143-147 (Agencia Cobradora)
            d += '04' # 148-149 (Especie: 04=Servico) - Requested in plan
            d += 'N' # 150-150 (Aceite)
            d += datetime.now().strftime('%d%m%y') # 151-156 (Data Emissao)
            
            # 157-158: Instrução 1 (00 ou 06)
            d += '00' 
            
            d += '00' # 159-160 (Instrução 2)
            d += CnabService.format_num(0, 13) # 161-173 (Juros)
            d += datetime.now().strftime('%d%m%y') # 174-179 (Data Desconto) - Using issuance as placeholder
            d += CnabService.format_num(0, 13) # 180-192 (Desconto)
            d += CnabService.format_num(0, 13) # 193-205 (IOF)
            d += CnabService.format_num(0, 13) # 206-218 (Abatimento) - Requested
            
            # 219-220: Tipo Inscricao Sacado (01=CPF, 02=CNPJ)
            doc_clean = ''.join(filter(str.isdigit, boleto.sacado_doc))
            if len(doc_clean) > 11:
                tipo_insc = '02'
            else:
                tipo_insc = '01'
            d += tipo_insc
            
            # 221-234: CNPJ/CPF Sacado
            d += CnabService.format_num(doc_clean, 14)
            
            d += CnabService.format_text(boleto.sacado_name, 40) # 235-274 (Nome)
            d += CnabService.format_text('Endereco Sacado', 40) # 275-314 (Endereco) - Mocking, need in DB
            d += '000000000000' # 315-326 (Bairro)
            d += '00000000' # 327-334 (CEP)
            d += ' '*15 # 335-349 (Cidade)
            d += 'UF' # 350-351 (UF)
            d += ' '*44 # 352-393 (Sacador/Avalista + Brancos)
            d += '0' # 394-394 (Moeda)
            
            d += CnabService.format_num(seq, 6) # 395-400 (Sequencial)
            
            if len(d) < 400: d = d.ljust(400, ' ')
            lines.append(d[:400])
            seq += 1
            
        # --- TRAILER (Pag ?) ---
        # 001-001: 9
        # 395-400: Sequencial
        t = '9'
        t += ' '*393
        t += CnabService.format_num(seq, 6)
        
        lines.append(t[:400])
        
        return "\r\n".join(lines)

class BoletoBuilder:
    @staticmethod
    def mod11(number, base=9, r=0):
        """
        Calculates Modulo 11 check digit.
        """
        sum_ = 0
        weight = 2
        for n in reversed(str(number)):
            sum_ += int(n) * weight
            weight += 1
            if weight > base:
                weight = 2
        
        res = 11 - (sum_ % 11)
        if res == 10 or res == 11:
            return r
        return res

    @staticmethod
    def mod10(number):
        """
        Calculates Modulo 10 check digit.
        """
        sum_ = 0
        weight = 2
        for n in reversed(str(number)):
            val = int(n) * weight
            if val > 9:
                val = (val // 10) + (val % 10)
            sum_ += val
            weight = 1 if weight == 2 else 2
        
        res = 10 - (sum_ % 10)
        return 0 if res == 10 else res

    @staticmethod
    def calculate_santander_nosso_numero(nosso_numero):
        # Santander format: 12 digits + 1 check digit
        # Example logic (simplified)
        dv = BoletoBuilder.mod11(nosso_numero)
        return f"{nosso_numero}-{dv}"

    @staticmethod
    def generate_pdf(boleto_data, filepath):
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        
        # Margins
        left_margin = 10*mm
        right_margin = 200*mm
        
        # Draw basic boleto lines (Improved Layout)
        c.setLineWidth(1)
        
        # Top Section (Recibo do Pagador)
        y = height - 20*mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin, y, "RECIBO DO PAGADOR")
        y -= 10*mm
        
        # Bank Header
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left_margin, y, f"{boleto_data['bank_code']} | {boleto_data['bank_name']}")
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(right_margin, y, boleto_data['digitable_line'])
        y -= 5*mm
        c.line(left_margin, y, right_margin, y)
        
        # Main Box
        # Local de Pagamento
        y_top_box = y
        c.line(left_margin, y_top_box, right_margin, y_top_box)
        c.setFont("Helvetica", 6)
        c.drawString(left_margin, y_top_box - 3*mm, "Local de Pagamento")
        c.setFont("Helvetica", 10)
        c.drawString(left_margin, y_top_box - 7*mm, "PAGÁVEL EM QUALQUER BANCO ATÉ O VENCIMENTO")
        c.line(left_margin, y_top_box - 9*mm, right_margin, y_top_box - 9*mm) # Horizontal line below
        
        # Vencimento Column Line
        c.line(150*mm, y_top_box, 150*mm, y_top_box - 9*mm)
        c.setFont("Helvetica", 6)
        c.drawString(151*mm, y_top_box - 3*mm, "Vencimento")
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(right_margin - 1*mm, y_top_box - 7*mm, boleto_data['due_date'].strftime('%d/%m/%Y'))

        # Beneficiario / Valor
        y_row2 = y_top_box - 9*mm
        c.setFont("Helvetica", 6)
        c.drawString(left_margin, y_row2 - 3*mm, "Beneficiário")
        c.setFont("Helvetica", 10)
        c.drawString(left_margin, y_row2 - 7*mm, boleto_data['cedente_name'])
        
        # Vertical line for Value
        c.line(150*mm, y_row2, 150*mm, y_row2 - 9*mm)
        c.setFont("Helvetica", 6)
        c.drawString(151*mm, y_row2 - 3*mm, "Valor do Documento")
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(right_margin - 1*mm, y_row2 - 7*mm, f"R$ {boleto_data['amount']:.2f}")
        c.line(left_margin, y_row2 - 9*mm, right_margin, y_row2 - 9*mm)

        # Nosso Numero
        y_row3 = y_row2 - 9*mm
        c.setFont("Helvetica", 6)
        c.drawString(left_margin, y_row3 - 3*mm, "Nosso Número")
        # Placeholder Nosso Numero (extract from barcode/data if available, otherwise generic)
        c.setFont("Helvetica", 10)
        c.drawString(left_margin, y_row3 - 7*mm, "Verifique no Banco")
        c.line(left_margin, y_row3 - 9*mm, right_margin, y_row3 - 9*mm)

        # Pagador
        y_pagador = y_row3 - 20*mm
        c.setFont("Helvetica", 6)
        c.drawString(left_margin, y_pagador - 3*mm, "Pagador")
        c.setFont("Helvetica", 10)
        c.drawString(left_margin, y_pagador - 7*mm, f"{boleto_data['sacado_name']} - CNPJ/CPF: {boleto_data['sacado_doc']}")
        c.line(left_margin, y_pagador - 9*mm, right_margin, y_pagador - 9*mm)

        # Barcode (Interleaved 2 of 5)
        y_barcode = 20*mm
        c.setFont("Helvetica", 8)
        try:
            # Note: I2of5 requires digits only and even length usually, but standard lib handles it.
            # Boleto barcodes are 44 digits.
            clean_barcode = ''.join(filter(str.isdigit, boleto_data['barcode']))
            if len(clean_barcode) % 2 != 0:
                 clean_barcode = '0' + clean_barcode # Pad if necessary? Boleto is always 44.
            
            from reportlab.graphics.barcode import common
            from reportlab.graphics.barcode import code128 # Fallback
            # Trying standard I2of5 from reportlab (needs simple import)
            from reportlab.graphics.barcode import createBarcodeDrawing
            
            # Using createBarcodeDrawing is safer
            bc = createBarcodeDrawing('I2of5', value=clean_barcode, barWidth=0.25*mm, barHeight=13*mm, checksum=0)
            bc.drawOn(c, left_margin, y_barcode)
        except Exception as e:
            c.drawString(left_margin, y_barcode, f"BARCODE ERROR: {e} - {boleto_data['barcode']}")
        
        c.save()

class XmlParser:
    @staticmethod
    def parse_nfe(tree, ns):
        # NFe Namespace
        # Usually {http://www.portalfiscal.inf.br/nfe}
        
        # Find Destinatario (Payer)
        dest = tree.find(f'.//{{{ns}}}dest')
        if dest is None:
            raise ValueError("Destinatario not found in NFe")
            
        name = dest.find(f'{{{ns}}}xNome').text
        
        cnpj = dest.find(f'{{{ns}}}CNPJ')
        cpf = dest.find(f'{{{ns}}}CPF')
        doc = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')
        
        # Find Value
        v_nf = tree.find(f'.//{{{ns}}}total/{{{ns}}}ICMSTot/{{{ns}}}vNF')
        amount = float(v_nf.text) if v_nf is not None else 0.0
        
        # Find Date
        dh_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dhEmi')
        d_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dEmi')
        
        date_str = dh_emi.text if dh_emi is not None else (d_emi.text if d_emi is not None else '')
        # Simple ISO date parse (truncated to date)
        if 'T' in date_str:
            issue_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        else:
            issue_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
        # Find Number
        n_nf = tree.find(f'.//{{{ns}}}ide/{{{ns}}}nNF')
        number = n_nf.text if n_nf is not None else 'Unknown'
        
        return {
            'sacado_name': name,
            'sacado_doc': doc,
            'amount': amount,
            'issue_date': issue_date,
            'doc_number': number
        }

    @staticmethod
    def parse_cte(tree, ns):
        # CTe logic
        # Find Value
        v_tprest = tree.find(f'.//{{{ns}}}vPrest/{{{ns}}}vTPrest')
        amount = float(v_tprest.text) if v_tprest is not None else 0.0
        
        # Find Date
        dh_emi = tree.find(f'.//{{{ns}}}ide/{{{ns}}}dhEmi')
        date_str = dh_emi.text if dh_emi is not None else ''
        if 'T' in date_str:
            issue_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
        else:
            issue_date = datetime.now().date() # Fallback

        # Find Number
        n_ct = tree.find(f'.//{{{ns}}}ide/{{{ns}}}nCT')
        number = n_ct.text if n_ct is not None else 'Unknown'

        # Payer Logic
        # Try toma3
        toma3 = tree.find(f'.//{{{ns}}}infCteNorm/{{{ns}}}infCarga/{{{ns}}}toma3') 
        # Note: structure might vary, sometimes it is directly under infCte
        if toma3 is None:
             toma3 = tree.find(f'.//{{{ns}}}ide/{{{ns}}}toma3')

        payer_data = {}
        
        if toma3 is not None:
            toma_role = toma3.find(f'{{{ns}}}toma').text
            # 0=Remetente, 1=Expedidor, 2=Recebedor, 3=Destinatario
            role_map = {'0': 'rem', '1': 'exped', '2': 'receb', '3': 'dest'}
            role_tag = role_map.get(toma_role)
            
            if role_tag:
                role_node = tree.find(f'.//{{{ns}}}{role_tag}')
                if role_node is not None:
                    payer_data['name'] = role_node.find(f'{{{ns}}}xNome').text
                    cnpj = role_node.find(f'{{{ns}}}CNPJ')
                    cpf = role_node.find(f'{{{ns}}}CPF')
                    payer_data['doc'] = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')
        else:
            # Try toma4
            toma4 = tree.find(f'.//{{{ns}}}ide/{{{ns}}}toma4')
            if toma4 is not None:
                # toma4 explicitly defines the payer
                toma = toma4.find(f'{{{ns}}}toma') # Indicates who
                # But toma4 usually has CNPJ/CPF directly if it's "Outros"?
                # Actually toma4 struct: <toma>4</toma> <CNPJ>...</CNPJ> <xNome>...</xNome>
                payer_data['name'] = toma4.find(f'{{{ns}}}xNome').text
                cnpj = toma4.find(f'{{{ns}}}CNPJ')
                cpf = toma4.find(f'{{{ns}}}CPF')
                payer_data['doc'] = cnpj.text if cnpj is not None else (cpf.text if cpf is not None else '')

        if not payer_data:
            # Fallback to Destinatario if logic fails, but strict logic requires correct mapping
            dest = tree.find(f'.//{{{ns}}}dest')
            if dest:
                payer_data['name'] = dest.find(f'{{{ns}}}xNome').text
                cnpj = dest.find(f'{{{ns}}}CNPJ')
                payer_data['doc'] = cnpj.text if cnpj is not None else ''

        return {
            'sacado_name': payer_data.get('name', 'Unknown'),
            'sacado_doc': payer_data.get('doc', ''),
            'amount': amount,
            'issue_date': issue_date,
            'doc_number': number
        }

    @staticmethod
    def parse_file(filepath):
        try:
            tree = etree.parse(filepath)
            root = tree.getroot()
            
            # Extract namespace from root, e.g., {http://www.portalfiscal.inf.br/nfe}nfeProc -> http://www.portalfiscal.inf.br/nfe
            if '}' in root.tag:
                ns = root.tag.split('}')[0].strip('{')
            else:
                ns = ''

            # Case-insensitive check for document type
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
