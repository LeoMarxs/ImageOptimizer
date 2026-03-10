import os
import sys
import json
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

from PIL import Image, ImageOps
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipos / Constantes
# ---------------------------------------------------------------------------
Formato = Literal["webp", "jpeg", "png"]

EXTENSOES_ENTRADA: tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".avif",
)

EXT_SAIDA: dict[str, str] = {
    "webp": ".webp",
    "jpeg": ".jpg",
    "png":  ".png",
}


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------
@dataclass
class ResultadoArquivo:
    arquivo: str
    sucesso: bool
    tamanho_original: int = 0
    tamanho_final: int = 0
    erro: str = ""

    @property
    def reducao_pct(self) -> float:
        if self.tamanho_original == 0:
            return 0.0
        return (1 - self.tamanho_final / self.tamanho_original) * 100


@dataclass
class Relatorio:
    total: int = 0
    sucesso: int = 0
    falha: int = 0
    bytes_original: int = 0
    bytes_final: int = 0
    detalhes: list[ResultadoArquivo] = field(default_factory=list)

    @property
    def reducao_total_pct(self) -> float:
        if self.bytes_original == 0:
            return 0.0
        return (1 - self.bytes_final / self.bytes_original) * 100

    @property
    def economia_mb(self) -> float:
        return (self.bytes_original - self.bytes_final) / (1024 * 1024)


# ---------------------------------------------------------------------------
# Núcleo de processamento
# ---------------------------------------------------------------------------
def _processar_arquivo(
    caminho_in: Path,
    caminho_out: Path,
    formato: Formato,
    qualidade: int,
    largura_maxima: int,
    altura_maxima: int,
    manter_metadados: bool,
) -> ResultadoArquivo:
    """Processa um único arquivo de imagem. Thread-safe."""
    tamanho_original = caminho_in.stat().st_size

    try:
        with Image.open(caminho_in) as img:
            # 1. Corrige orientação EXIF
            img = ImageOps.exif_transpose(img)

            # 2. Redimensionamento respeitando proporção
            if img.width > largura_maxima or img.height > altura_maxima:
                img.thumbnail((largura_maxima, altura_maxima), Image.LANCZOS)

            # 3. Conversão de modo de cor
            if formato == "jpeg":
                # JPEG não suporta alpha — achata sobre branco
                if img.mode in ("RGBA", "P", "LA"):
                    fundo = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    fundo.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = fundo
                elif img.mode != "RGB":
                    img = img.convert("RGB")

            elif formato == "webp":
                # WebP suporta RGBA; converte P → RGBA para preservar transparência
                if img.mode == "P":
                    img = img.convert("RGBA")
                elif img.mode not in ("RGB", "RGBA", "L"):
                    img = img.convert("RGB")

            elif formato == "png":
                # PNG suporta todos os modos; mantém como está ou converte CMYK
                if img.mode == "CMYK":
                    img = img.convert("RGB")

            # 4. Metadados EXIF (opcional)
            exif_bytes = b""
            if manter_metadados:
                try:
                    exif_bytes = img.info.get("exif", b"")
                except Exception:
                    pass

            # 5. Salvamento
            save_kwargs: dict = {}

            if formato == "webp":
                save_kwargs = {
                    "format": "WEBP",
                    "quality": qualidade,
                    "method": 6,       # melhor compressão (mais lento)
                    "lossless": False,
                }
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes

            elif formato == "jpeg":
                save_kwargs = {
                    "format": "JPEG",
                    "quality": qualidade,
                    "optimize": True,
                    "progressive": True,
                    "subsampling": 2,   # 4:2:0 — menor tamanho
                }
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes

            elif formato == "png":
                save_kwargs = {
                    "format": "PNG",
                    "optimize": True,
                    "compress_level": 9,   # compressão máxima (sem perda)
                }

            caminho_out.parent.mkdir(parents=True, exist_ok=True)
            img.save(caminho_out, **save_kwargs)

        tamanho_final = caminho_out.stat().st_size
        return ResultadoArquivo(
            arquivo=caminho_in.name,
            sucesso=True,
            tamanho_original=tamanho_original,
            tamanho_final=tamanho_final,
        )

    except Exception as exc:
        # Remove arquivo corrompido que possa ter sido criado
        if caminho_out.exists():
            caminho_out.unlink(missing_ok=True)
        return ResultadoArquivo(
            arquivo=caminho_in.name,
            sucesso=False,
            tamanho_original=tamanho_original,
            erro=str(exc),
        )


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------
def otimizar_imagens(
    pasta_origem: str | Path,
    pasta_destino: str | Path,
    formato: Formato = "webp",
    qualidade: int = 75,
    largura_maxima: int = 1920,
    altura_maxima: int = 1920,
    manter_metadados: bool = True,
    sobrescrever: bool = False,
    workers: int = 4,
    salvar_relatorio: bool = False,
) -> Relatorio:
    """
    Comprime e converte imagens de *pasta_origem* para *pasta_destino*.

    Parâmetros
    ----------
    pasta_origem      : Pasta com as imagens originais.
    pasta_destino     : Pasta onde serão salvas as imagens processadas.
    formato           : 'webp' | 'jpeg' | 'png'
    qualidade         : 1–95 (apenas para webp/jpeg; png usa compressão sem perdas).
    largura_maxima    : Largura máxima em pixels (mantém proporção).
    altura_maxima     : Altura máxima em pixels (mantém proporção).
    manter_metadados  : Preserva dados EXIF (localização, câmera, etc.).
    sobrescrever      : Se False, pula arquivos que já existem no destino.
    workers           : Número de threads paralelas.
    salvar_relatorio  : Grava um JSON com o relatório completo no destino.
    """
    pasta_origem = Path(pasta_origem)
    pasta_destino = Path(pasta_destino)

    if not pasta_origem.exists():
        raise FileNotFoundError(f"Pasta de origem não encontrada: {pasta_origem}")

    pasta_destino.mkdir(parents=True, exist_ok=True)

    # Coleta arquivos
    arquivos: list[Path] = [
        f for f in pasta_origem.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSOES_ENTRADA
    ]

    if not arquivos:
        log.warning("Nenhum arquivo de imagem encontrado em '%s'.", pasta_origem)
        return Relatorio()

    ext_saida = EXT_SAIDA[formato.lower()]
    relatorio = Relatorio(total=len(arquivos))

    log.info("Encontrados %d arquivo(s). Convertendo para %s…", len(arquivos), formato.upper())

    tarefas: list[tuple[Path, Path]] = []
    for arq in arquivos:
        destino = pasta_destino / (arq.stem + ext_saida)
        if not sobrescrever and destino.exists():
            log.debug("Pulando (já existe): %s", destino.name)
            relatorio.total -= 1
            continue
        tarefas.append((arq, destino))

    if not tarefas:
        log.info("Todos os arquivos já foram processados. Use sobrescrever=True para reprocessar.")
        return relatorio

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {
            pool.submit(
                _processar_arquivo,
                arq, dest, formato, qualidade,
                largura_maxima, altura_maxima, manter_metadados,
            ): arq
            for arq, dest in tarefas
        }

        with tqdm(total=len(futuros), desc="Processando", unit="img") as barra:
            for futuro in as_completed(futuros):
                resultado: ResultadoArquivo = futuro.result()
                relatorio.detalhes.append(resultado)

                if resultado.sucesso:
                    relatorio.sucesso += 1
                    relatorio.bytes_original += resultado.tamanho_original
                    relatorio.bytes_final += resultado.tamanho_final
                else:
                    relatorio.falha += 1
                    log.warning("Falha em '%s': %s", resultado.arquivo, resultado.erro)

                barra.update(1)

    # Relatório resumido
    log.info("─" * 50)
    log.info("✅  Sucesso : %d / %d", relatorio.sucesso, len(tarefas))
    if relatorio.falha:
        log.warning("❌  Falhas  : %d", relatorio.falha)
    log.info(
        "📦  Tamanho : %.1f MB → %.1f MB  (economia de %.1f%%)",
        relatorio.bytes_original / 1e6,
        relatorio.bytes_final / 1e6,
        relatorio.reducao_total_pct,
    )
    log.info("─" * 50)

    # Grava JSON se solicitado
    if salvar_relatorio:
        caminho_json = pasta_destino / "_relatorio_compressao.json"
        dados = {
            "total": relatorio.total,
            "sucesso": relatorio.sucesso,
            "falha": relatorio.falha,
            "reducao_pct": round(relatorio.reducao_total_pct, 2),
            "economia_mb": round(relatorio.economia_mb, 3),
            "arquivos": [
                {
                    "arquivo": r.arquivo,
                    "sucesso": r.sucesso,
                    "original_kb": round(r.tamanho_original / 1024, 1),
                    "final_kb": round(r.tamanho_final / 1024, 1),
                    "reducao_pct": round(r.reducao_pct, 1),
                    "erro": r.erro,
                }
                for r in relatorio.detalhes
            ],
        }
        caminho_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2))
        log.info("Relatório salvo em: %s", caminho_json)

    return relatorio


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Compressor e conversor de imagens para web.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("origem",  help="Pasta com as imagens originais")
    parser.add_argument("destino", help="Pasta de saída")
    parser.add_argument("-f", "--formato",   default="webp", choices=["webp", "jpeg", "png"],
                        help="Formato de saída")
    parser.add_argument("-q", "--qualidade", default=75, type=int, metavar="1-95",
                        help="Qualidade (webp/jpeg). PNG ignora este parâmetro.")
    parser.add_argument("-W", "--largura",   default=1920, type=int,
                        help="Largura máxima em pixels")
    parser.add_argument("-H", "--altura",    default=1920, type=int,
                        help="Altura máxima em pixels")
    parser.add_argument("--sem-metadados",   action="store_true",
                        help="Remove dados EXIF das imagens")
    parser.add_argument("--sobrescrever",    action="store_true",
                        help="Reprocessa arquivos já existentes no destino")
    parser.add_argument("-w", "--workers",   default=4, type=int,
                        help="Número de threads paralelas")
    parser.add_argument("--relatorio",       action="store_true",
                        help="Salva relatório JSON na pasta de destino")

    args = parser.parse_args()

    if not (1 <= args.qualidade <= 95):
        parser.error("Qualidade deve estar entre 1 e 95.")

    otimizar_imagens(
        pasta_origem=args.origem,
        pasta_destino=args.destino,
        formato=args.formato,
        qualidade=args.qualidade,
        largura_maxima=args.largura,
        altura_maxima=args.altura,
        manter_metadados=not args.sem_metadados,
        sobrescrever=args.sobrescrever,
        workers=args.workers,
        salvar_relatorio=args.relatorio,
    )


if __name__ == "__main__":
    # ── Uso direto (sem CLI) ──────────────────────────────────────────────
    # Descomente e ajuste conforme necessário:
    #
    # otimizar_imagens(
    #     pasta_origem="fotos_originais",
    #     pasta_destino="fotos_prontas_site",
    #     formato="webp",
    #     qualidade=75,
    #     salvar_relatorio=True,
    # )

    # ── Uso via linha de comando ──────────────────────────────────────────
    # python otimizar_imagens.py fotos_originais fotos_prontas_site -f webp -q 75 --relatorio
    _cli()