"""
Carregador para Parquet particionado.
"""
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ParquetLoader:
    """Salva dados em formato Parquet particionado."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        pipeline_config = config.get("pipeline", {})
        self.paths = pipeline_config.get("paths", {})
        self.raw_path = Path(self.paths.get("raw", "data/raw"))
        self.staging_path = Path(self.paths.get("staging", "data/staging"))
        self.serving_path = Path(self.paths.get("serving", "data/serving"))
        self.output_format = pipeline_config.get("output_format", "parquet")
        self.partition_by = pipeline_config.get("partition_by", "date")
    
    def _get_serving_path(self, domain: str, subdomain: str) -> Path:
        """Retorna caminho de serving para um domínio/subdomínio."""
        return self.serving_path / domain / subdomain
    
    def _get_staging_path(self, domain: str, subdomain: str) -> Path:
        """Retorna caminho de staging para um domínio/subdomínio."""
        return self.staging_path / domain / subdomain
    
    def save_partitioned(
        self,
        data: List[Dict[str, Any]],
        domain: str,
        subdomain: str,
        partition_cols: List[str] = None
    ) -> Dict[str, Any]:
        """
        Salva dados em Parquet particionado.
        
        Args:
            data: Lista de dicionários com os dados
            domain: Domínio (clima, crypto, economia)
            subdomain: Subdomínio (diario, horario, historico)
            partition_cols: Colunas para particionamento
            
        Returns:
            Dicionário com estatísticas da escrita
        """
        if not data:
            logger.warning(f"Nenhum dado para salvar: {domain}.{subdomain}")
            return {"rows": 0, "files": 0, "path": "", "success": True}
        
        df = pd.DataFrame(data)
        
        # Determina colunas de partição
        if partition_cols is None:
            partition_cols = [self.partition_by]
        
        # Garante que colunas de partição existem
        for col in partition_cols:
            if col not in df.columns:
                logger.warning(f"Coluna de partição '{col}' não encontrada em {domain}.{subdomain}")
                partition_cols = [c for c in partition_cols if c in df.columns]
                break
        
        # Caminho de saída
        output_path = self._get_serving_path(domain, subdomain)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Converte para PyArrow Table
        table = pa.Table.from_pandas(df)
        
        # Escreve particionado
        try:
            pq.write_to_dataset(
                table,
                root_path=str(output_path),
                partition_cols=partition_cols if partition_cols else None,
                compression="snappy",
                use_dictionary=True,
                write_statistics=True
            )
            
            # Conta arquivos gerados
            parquet_files = list(output_path.rglob("*.parquet"))
            
            result = {
                "rows": len(df),
                "files": len(parquet_files),
                "path": str(output_path),
                "partition_cols": partition_cols,
                "success": True
            }
            
            logger.info(f"Salvo: {domain}.{subdomain} - {len(df)} linhas, {len(parquet_files)} arquivos em {output_path}")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao salvar {domain}.{subdomain}: {e}")
            return {"rows": 0, "files": 0, "path": str(output_path), "success": False, "error": str(e)}
    
    def save_raw(self, data: List[Dict[str, Any]], domain: str, filename: str) -> Path:
        """Salva dados brutos (JSON/CSV) na zona raw."""
        if not data:
            return None
        
        df = pd.DataFrame(data)
        output_path = self.raw_path / domain
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_path = output_path / filename
        
        if self.output_format == "parquet":
            df.to_parquet(file_path, compression="snappy", index=False)
        else:
            df.to_csv(file_path, index=False, encoding="utf-8")
        
        logger.info(f"Raw salvo: {file_path} ({len(df)} linhas)")
        return file_path
    
    def read_partitioned(self, domain: str, subdomain: str, filters: List = None) -> pd.DataFrame:
        """Lê dados particionados de volta."""
        path = self._get_serving_path(domain, subdomain)
        
        if not path.exists():
            return pd.DataFrame()
        
        dataset = pq.ParquetDataset(str(path), filters=filters)
        return dataset.read().to_pandas()