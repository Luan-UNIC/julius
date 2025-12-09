# CHANGELOG - Sistema FIDC Julius

## [2.1.0] - 09/12/2025

### 🎯 Foco Prioritário: Banco BMP/FiBank com Contas Escrow

Esta versão implementa correções críticas e melhorias focadas no suporte completo ao banco BMP Money Plus (código 274) com suporte a contas escrow por cedente.

---

## ✨ Novas Funcionalidades

### 1. **Validação de CPF/CNPJ**
- ✅ Implementado arquivo `validation.py` com funções completas de validação
- ✅ Validação de CPF com cálculo de dígitos verificadores
- ✅ Validação de CNPJ com cálculo de dígitos verificadores
- ✅ Funções de formatação: `format_cpf()` e `format_cnpj()`
- ✅ Função unificada: `validate_cpf_cnpj()` (detecta automaticamente pelo tamanho)

**Exemplo de uso:**
```python
from validation import validate_cpf_cnpj, format_cpf

if validate_cpf_cnpj("12345678901"):
    formatted = format_cpf("12345678901")  # 123.456.789-01
```

### 2. **Persistência de Arquivos CNAB**
- ✅ Criado novo modelo `CNABFile` para armazenar metadados dos arquivos gerados
- ✅ Arquivos CNAB agora salvos em disco na pasta `/cnab_files/`
- ✅ Registro automático no banco de dados com:
  - Filename
  - File path
  - Sequencial de remessa
  - Contagem de boletos
  - Valor total
  - Data de criação
- ✅ Histórico de transações para auditoria completa

### 3. **Sequencial de Remessa por Banco/Cedente**
- ✅ Adicionado campo `sequencial_remessa` no modelo `BankConfig`
- ✅ Incremento automático e atômico (com lock pessimista) a cada geração
- ✅ Sequencial independente por banco e por cedente
- ✅ Nomenclatura correta dos arquivos: `CBDDMMSSSS.REM`
  - CB = Cobrança Boleto
  - DD = Dia
  - MM = Mês
  - SSSS = Sequencial (00001, 00002...)

**Exemplo:** 
- Primeiro arquivo: `CB091200001.REM`
- Segundo arquivo: `CB091200002.REM`

### 4. **SECRET_KEY Seguro**
- ✅ Geração de SECRET_KEY aleatória e criptograficamente segura
- ✅ Configuração via variável de ambiente (.env)
- ✅ Arquivo `.env.example` para referência
- ✅ Integração com `python-dotenv`
- ✅ Fallback para ambiente de desenvolvimento

---

## 🔧 Correções Críticas

### 1. **Código de Barras BMP Corrigido**
**Problema:** O método `calculate_barcode()` estava hardcoded para Santander, gerando códigos inválidos para BMP.

**Solução:**
- ✅ Implementado campo livre específico do BMP (25 posições):
  - Posições 20-23: Agência (4 dígitos, SEM DV)
  - Posições 24-25: Código da Carteira (2 dígitos)
  - Posições 26-36: Nosso Número (11 dígitos, SEM DV)
  - Posições 37-43: Conta Corrente (7 dígitos, SEM DV)
  - Posição 44: Zero fixo
- ✅ Novo parâmetro `bank_type` no método `calculate_barcode()`
- ✅ Suporte simultâneo para Santander (033) e BMP (274)

**Antes:**
```python
# Sempre usava campo livre Santander
free_field = '9' + carteira + nosso_numero
```

**Depois:**
```python
if bank_type == 'bmp':
    # Campo livre BMP correto
    free_field = agency + carteira + nosso_numero + account + '0'
else:
    # Campo livre Santander
    free_field = '9' + carteira + nosso_numero + '0' * 9
```

### 2. **Geração de CNAB 400 BMP Corrigida**

**Melhorias implementadas:**
- ✅ Código da empresa alinhado à **direita** com zeros à **esquerda** (posições 027-046)
- ✅ Sequencial de remessa correto no header (posições 111-117)
- ✅ Identificação do beneficiário no banco formatada corretamente (posições 021-037):
  - Zero fixo + Carteira(3) + Agência(5) + Conta(7) + Dígito(1)
- ✅ Nosso Número com DV calculado por Módulo 11 base 7
- ✅ Campo Multa e Percentual implementados (posições 066-070)
- ✅ Todos os campos obrigatórios preenchidos conforme especificação

**Campos FIDC (Sacador/Avalista):**
- ✅ Tipo Sacador/Avalista (posição 335)
- ✅ CPF/CNPJ Sacador (posições 336-350)
- ✅ Nome Sacador/Avalista (posições 351-394)

### 3. **Geração de CNAB 240 Santander Melhorada**
- ✅ Sequencial de arquivo implementado
- ✅ Retorno de tupla (content, filename) para consistência
- ✅ Persistência de arquivos em disco

---

## 🏦 Suporte a Contas Escrow

O modelo `BankConfig` já suportava múltiplas configurações bancárias por cedente, permitindo:

✅ **Múltiplas contas BMP por cedente**
- Cada cedente pode ter sua própria conta escrow BMP
- Configuração independente de:
  - Agência
  - Conta corrente
  - Carteira
  - Convênio (código da empresa)
  - Limites de Nosso Número
  - Instruções financeiras (juros, multa, desconto, protesto, baixa)

✅ **Geração de CNAB com conta correta**
- O sistema usa automaticamente a configuração BMP do cedente
- Nosso Número independente por conta escrow
- Sequencial de remessa independente por conta

---

## 📋 Migração do Banco de Dados

### Script: `migrate_db_v2.py`

**Alterações aplicadas:**
1. Adição da coluna `sequencial_remessa` em `bank_config` (default: 1)
2. Criação da tabela `cnab_file`:
   - `id` (PK)
   - `user_id` (FK para user)
   - `bank_type` (santander/bmp)
   - `filename`
   - `file_path`
   - `sequencial`
   - `boleto_count`
   - `total_amount`
   - `created_at`

**Executar migração:**
```bash
python3 migrate_db_v2.py
```

---

## 🔐 Configuração de Segurança

### Arquivo `.env`

Criar arquivo `.env` na raiz do projeto com:

```env
# Flask Secret Key (OBRIGATÓRIO)
SECRET_KEY=<sua_chave_secreta_aqui>

# Database
SQLALCHEMY_DATABASE_URI=sqlite:///fidc.db

# Folders
UPLOAD_FOLDER=uploads
CNAB_FOLDER=cnab_files

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
```

**Gerar nova SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📦 Dependências Atualizadas

Adicionado ao `requirements.txt`:
- `python-dotenv` - Carregamento de variáveis de ambiente

**Instalar dependências:**
```bash
pip install -r requirements.txt
```

---

## 🧪 Testes

### Script de teste: `test_validation.py`

Testa:
- ✅ Validação de CPF
- ✅ Validação de CNPJ
- ✅ Formatação de CPF/CNPJ
- ✅ Geração de código de barras BMP (44 dígitos)
- ✅ Geração de código de barras Santander (44 dígitos)
- ✅ Cálculo de DV para Nosso Número BMP (Módulo 11 base 7)

**Executar testes:**
```bash
python3 test_validation.py
```

---

## 📂 Novos Arquivos

### Arquivos Criados:
1. **`validation.py`** - Funções de validação de CPF/CNPJ
2. **`migrate_db_v2.py`** - Script de migração do banco de dados
3. **`test_validation.py`** - Script de testes automatizados
4. **`.env.example`** - Exemplo de configuração de ambiente
5. **`.env`** - Configuração de ambiente (não versionar!)
6. **`CHANGELOG.md`** - Este arquivo

### Arquivos Modificados:
1. **`models.py`** - Adicionado `CNABFile` e campo `sequencial_remessa`
2. **`services.py`** - Corrigido código de barras BMP e geração CNAB
3. **`app.py`** - Integração com .env, persistência de CNAB, sequencial
4. **`requirements.txt`** - Adicionado `python-dotenv`

---

## 🎯 Compatibilidade

### Mantida compatibilidade com:
- ✅ Santander (CNAB 240) - código 033
- ✅ BMP Money Plus (CNAB 400) - código 274
- ✅ Sistema de autenticação existente
- ✅ Dashboards de cedente e agente
- ✅ Todas as funcionalidades anteriores

---

## 📈 Melhorias de Auditoria

### Logs de Transação Expandidos:
- ✅ Geração de CNAB registrada com:
  - Filename
  - Banco
  - Tipo de CNAB (240/400)
  - Quantidade de boletos
  - Valor total
  - Sequencial

### Histórico Completo:
- ✅ Todos os arquivos CNAB gerados ficam salvos em `/cnab_files/`
- ✅ Registro no banco de dados para consulta futura
- ✅ Rastreabilidade completa para auditoria

---

## ⚠️ Notas Importantes

### 1. **Sequencial de Remessa**
- O sequencial inicia em `1` para cada novo banco configurado
- É incrementado automaticamente a cada geração de arquivo
- **NÃO** deve ser resetado manualmente
- **NÃO** deve ser repetido (causa rejeição pelo banco)

### 2. **Contas Escrow BMP**
- Cada cedente deve ter sua própria configuração BMP
- O campo `convenio` deve conter o código da empresa fornecido pelo BMP
- Este código é alinhado à direita com zeros à esquerda no CNAB

### 3. **Arquivos CNAB**
- Salvos em `/cnab_files/` com nomenclatura padrão
- Encoding: ISO-8859-1 (padrão bancário brasileiro)
- Line ending: CRLF (Windows - padrão bancário)

### 4. **SECRET_KEY**
- **CRÍTICO**: Alterar a SECRET_KEY padrão em produção
- Nunca versionar o arquivo `.env` no Git
- Adicionar `.env` ao `.gitignore`

---

## 🔄 Processo de Deploy

1. **Fazer backup do banco de dados:**
   ```bash
   cp instance/fidc.db instance/fidc.db.backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **Atualizar código:**
   ```bash
   git pull origin main
   ```

3. **Instalar dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar .env:**
   ```bash
   cp .env.example .env
   # Editar .env com valores corretos
   ```

5. **Executar migração:**
   ```bash
   python3 migrate_db_v2.py
   ```

6. **Executar testes:**
   ```bash
   python3 test_validation.py
   ```

7. **Reiniciar aplicação**

---

## 🐛 Bugs Corrigidos

1. ✅ Código de barras BMP gerado incorretamente (campo livre errado)
2. ✅ Linha digitável BMP com valores incorretos
3. ✅ Sequencial de remessa sempre 1 (causava duplicação de nomes)
4. ✅ Arquivos CNAB não persistidos (perdidos após download)
5. ✅ SECRET_KEY inseguro hardcoded no código
6. ✅ Sem validação de CPF/CNPJ (aceitava documentos inválidos)

---

## 🚀 Próximas Implementações Sugeridas

### Alta Prioridade:
- [ ] Processamento de arquivos de retorno CNAB
- [ ] Dashboard de histórico de arquivos CNAB gerados
- [ ] Validação de CPF/CNPJ nos formulários web
- [ ] Testes unitários completos

### Média Prioridade:
- [ ] Exportação de relatórios por cedente
- [ ] Alertas de limite de Nosso Número
- [ ] Backup automático de arquivos CNAB
- [ ] Suporte a outros bancos (Bradesco, Itaú, etc.)

### Baixa Prioridade:
- [ ] Interface para reenvio de arquivos CNAB
- [ ] Histórico de alterações de configuração bancária
- [ ] Dashboard de estatísticas de boletos

---

## 📞 Suporte

Para dúvidas sobre as implementações:
- Consultar `ANALISE_CODIGO.md` para estrutura do sistema
- Consultar `ESPECIFICACOES_CNAB.md` para detalhes técnicos CNAB
- Executar `test_validation.py` para validar instalação

---

**Desenvolvido por:** FIDC Development Team  
**Data:** 09 de Dezembro de 2025  
**Versão:** 2.1.0
