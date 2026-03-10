# 🗜️ ImagePress — Compressor de Imagens

> Compressor e conversor de imagens para web, disponível como **interface web** (HTML puro) e como **script Python** para uso em lote via terminal.

by [Leoarxs](https://github.com/Leoarxs)

---

## 📋 Índice

- [Como funciona](#-como-funciona)
- [Interface Web](#-interface-web)
- [Script Python](#-script-python)
- [Tecnologias utilizadas](#-tecnologias-utilizadas)
- [Como foi feito](#-como-foi-feito)
- [Estrutura do projeto](#-estrutura-do-projeto)

---

## ⚙️ Como funciona

O ImagePress comprime imagens reduzindo o tamanho do arquivo sem perda perceptível de qualidade, ideal para uso em sites e aplicações web. O processo envolve três etapas principais:

1. **Ingestão** — o usuário seleciona ou arrasta imagens (JPG, PNG, GIF, BMP, TIFF, WebP, AVIF)
2. **Processamento** — cada imagem é redimensionada (se necessário) e recodificada no formato escolhido com a qualidade definida
3. **Exportação** — os arquivos comprimidos ficam disponíveis para download individual ou em `.zip`

A economia de tamanho é exibida em tempo real para cada arquivo e no resumo geral (original vs. comprimido, % de redução).

---

## 🌐 Interface Web

### Como usar

1. Abra o arquivo `compressor_ui.html` em qualquer navegador moderno — **não precisa de servidor**
2. Arraste imagens para a área de drop ou clique para selecionar
3. Ajuste as configurações no painel lateral direito
4. Clique em **Comprimir imagens**
5. Baixe os arquivos individualmente ou clique em **Baixar tudo (.zip)**

### Configurações disponíveis

| Opção | Valores | Descrição |
|---|---|---|
| Formato de saída | `WebP` / `JPEG` / `PNG` | WebP oferece melhor compressão; PNG é sem perdas |
| Qualidade | 1 – 95 | Controla o balanço tamanho × fidelidade (não se aplica ao PNG) |
| Largura máxima | px | Redimensiona proporcionalmente se a imagem ultrapassar o limite |
| Altura máxima | px | Idem para altura |
| Preservar EXIF | on/off | Mantém ou remove metadados (localização, câmera, data) |
| Download automático | on/off | Salva cada arquivo assim que for processado |

### Formatos de entrada suportados

`JPG` `PNG` `GIF` `BMP` `TIFF` `WebP` `AVIF`

---

## 🐍 Script Python

### Requisitos

```bash
pip install Pillow tqdm
```

### Uso rápido

```bash
python otimizar_imagens.py fotos_originais fotos_prontas_site
```

### Uso avançado (CLI completa)

```bash
python otimizar_imagens.py <origem> <destino> [opções]

Opções:
  -f, --formato     webp | jpeg | png        (padrão: webp)
  -q, --qualidade   1-95                     (padrão: 75)
  -W, --largura     largura máxima em px     (padrão: 1920)
  -H, --altura      altura máxima em px      (padrão: 1920)
  --sem-metadados   remove dados EXIF
  --sobrescrever    reprocessa arquivos já existentes
  -w, --workers     threads paralelas        (padrão: 4)
  --relatorio       salva JSON com estatísticas no destino
```

### Exemplos

```bash
# Converter para WebP com qualidade 80
python otimizar_imagens.py ./fotos ./saida -f webp -q 80

# Gerar JPEGs limitados a 1280px e salvar relatório
python otimizar_imagens.py ./fotos ./saida -f jpeg -W 1280 -H 1280 --relatorio

# Processamento mais rápido com 8 threads
python otimizar_imagens.py ./fotos ./saida -w 8
```

### Uso como módulo

```python
from otimizar_imagens import otimizar_imagens

relatorio = otimizar_imagens(
    pasta_origem="fotos_originais",
    pasta_destino="fotos_prontas_site",
    formato="webp",
    qualidade=75,
    salvar_relatorio=True,
)

print(f"Economia: {relatorio.reducao_total_pct:.1f}%")
print(f"Espaço liberado: {relatorio.economia_mb:.2f} MB")
```

### Relatório JSON gerado

```json
{
  "total": 12,
  "sucesso": 12,
  "falha": 0,
  "reducao_pct": 68.4,
  "economia_mb": 14.72,
  "arquivos": [
    {
      "arquivo": "foto01.jpg",
      "sucesso": true,
      "original_kb": 3420.1,
      "final_kb": 891.3,
      "reducao_pct": 73.9,
      "erro": ""
    }
  ]
}
```

---

## 🛠️ Tecnologias utilizadas

### Interface Web

| Tecnologia | Uso |
|---|---|
| **HTML5 Canvas API** | Redimensionamento e recodificação das imagens no navegador |
| **Canvas.toBlob()** | Exportação nos formatos WebP, JPEG e PNG |
| **File API / FileReader** | Leitura e pré-visualização das imagens selecionadas |
| **JSZip** (CDN, carregado sob demanda) | Empacotamento dos arquivos em `.zip` |
| **CSS custom properties** | Sistema de tema consistente com variáveis |
| **CSS Grid + Flexbox** | Layout responsivo sem frameworks |
| **Google Fonts** | Tipografia: `Syne` (display) + `JetBrains Mono` (mono) |

> Nenhum framework JavaScript foi utilizado — a UI funciona com **vanilla JS puro**.

### Script Python

| Biblioteca | Uso |
|---|---|
| **Pillow (PIL)** | Abertura, manipulação, conversão e salvamento de imagens |
| `ImageOps.exif_transpose` | Correção automática de rotação baseada em metadados EXIF |
| **tqdm** | Barra de progresso no terminal |
| **concurrent.futures** | Processamento paralelo com `ThreadPoolExecutor` |
| **argparse** | Interface de linha de comando |
| **dataclasses** | Tipagem e estrutura dos resultados por arquivo |
| **pathlib** | Manipulação de caminhos de forma segura e multiplataforma |

---

## 🔨 Como foi feito

### Interface Web

A UI foi construída como um único arquivo HTML autocontido, sem dependências externas obrigatórias. O fluxo de compressão acontece inteiramente no navegador:

```
Arquivo selecionado
       ↓
  FileReader → cria ObjectURL
       ↓
  <img> carrega a imagem
       ↓
  <canvas> desenha com novo tamanho
       ↓
  canvas.toBlob(mime, quality)
       ↓
  Blob → download / zip
```

O design segue uma estética **industrial/dark** com grid sutil de fundo, tipografia contrastante (display bold + monospace leve) e cor de destaque amarelo-neon (`#e8ff47`). Cada decisão visual foi feita para comunicar precisão técnica sem ser genérica.

### Script Python

O script foi estruturado em três camadas:

1. **`_processar_arquivo()`** — função pura e thread-safe que processa uma única imagem. Trata todos os casos de modo de cor (RGBA, P, CMYK, LA) por formato de saída, aplica redimensionamento proporcional com `LANCZOS` e salva com os parâmetros otimizados para cada formato.

2. **`otimizar_imagens()`** — orquestrador principal. Descobre os arquivos, distribui o trabalho entre threads com `ThreadPoolExecutor`, agrega resultados em um `Relatorio` e exibe estatísticas.

3. **`_cli()`** — interface de terminal via `argparse`, que mapeia flags para os parâmetros da função principal.

Melhorias implementadas em relação à versão original:

- Correção do bug de transparência em JPEG (fundo branco explícito)
- Processamento paralelo (de sequencial para multi-thread)
- Suporte a mais formatos de entrada e saída
- Skip de arquivos já processados (`sobrescrever=False`)
- Tipagem com dataclasses para resultados

---

## 📁 Estrutura do projeto

```
imagepress/
├── compressor_ui.html      # Interface web (standalone, sem servidor)
├── otimizar_imagens.py     # Script Python para uso em lote
└── README.md               # Este arquivo
```

---

## 📄 Licença

MIT — livre para uso, modificação e distribuição.
