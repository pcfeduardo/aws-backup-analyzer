# AWS Backup Analyzer (ABA)

O **AWS Backup Analyzer (ABA)** é uma ferramenta que analisa backups configurados no AWS Backup, gerando relatórios detalhados em JSON e Excel para auxiliar analistas a compreenderem o estado de backups no ambiente AWS.

## Funcionalidades

- Analisa o estado dos backups em uma região específica da AWS.
- Gera relatórios detalhados em formato JSON e Excel.
- Fornece insights sobre:
  - Planos de backup e regras configuradas.
  - Recursos cobertos pelos backups.
  - Status de execução de jobs e recuperação.

## Pré-requisitos

Certifique-se de que você tem instalado:

- **Python 3.8 ou superior**
- **pip** para gerenciar pacotes Python


## Passo a passo de instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/pcfeduardo/aws-backup-analyzer.git
cd aws-backup-analyzer
```

### 2. Configurar o ambiente virtual
Configure o ambiente virtual (venv) para isolar dependências:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Sempre ative o ambiente virtual antes de executar o projeto.

### 3. Instalar dependências
Após ativar o ambiente virtual, instale as dependências:

```bash
pip install -r requirements.txt
```

## Como executar o script
Certifique-se de ter as credenciais da AWS configuradas corretamente no arquivo ~/.aws/credentials ou por variáveis de ambiente.

Execute o script principal:
```bash
python main.py
```

O script irá gerar:
* Um relatório JSON com as análises detalhadas.
* Um arquivo Excel, formatado para fácil interpretação.

## Estrutura de Saída
### JSON
Informações como:
* Resumo de jobs (e.g., COMPLETED, FAILED).
* Planos de backup e seleções configuradas.
* Recursos únicos e últimos backups realizados.

### Excel
Planilhas organizadas:
* Resumo geral dos backups
* Detalhes de recursos cobertos
* Status dos jobs

## Contribuições
Sinta-se à vontade para contribuir com melhorias. Abra issues ou envie pull requests.