import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Union, Optional, Any

logger = logging.getLogger(__name__)

def read_json_file(file_path: Union[str, Path]) -> Dict:
    """
    Lit un fichier JSON et retourne son contenu.

    Args:
        file_path: Chemin vers le fichier JSON

    Returns:
        Dict: Contenu du fichier JSON

    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        json.JSONDecodeError: Si le fichier n'est pas un JSON valide
    """
    try:
        file_path = Path(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Fichier non trouvé: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de décodage JSON pour {file_path}: {e}")
        raise

def write_json_file(file_path: Union[str, Path], data: Dict, indent: int = 4) -> bool:
    """
    Écrit des données dans un fichier JSON.

    Args:
        file_path: Chemin où enregistrer le fichier
        data: Données à enregistrer
        indent: Indentation du JSON (défaut: 4)

    Returns:
        bool: True si l'opération a réussi, False sinon
    """
    try:
        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture du fichier {file_path}: {e}")
        return False

def read_text_file(file_path: Union[str, Path]) -> str:
    """
    Lit le contenu d'un fichier texte.

    Args:
        file_path: Chemin vers le fichier texte

    Returns:
        str: Contenu du fichier

    Raises:
        FileNotFoundError: Si le fichier n'existe pas
    """
    try:
        file_path = Path(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Fichier non trouvé: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier {file_path}: {e}")
        raise

def write_text_file(file_path: Union[str, Path], content: str) -> bool:
    """
    Écrit du contenu dans un fichier texte.

    Args:
        file_path: Chemin où enregistrer le fichier
        content: Contenu à écrire

    Returns:
        bool: True si l'opération a réussi, False sinon
    """
    try:
        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture du fichier {file_path}: {e}")
        return False

def find_files(directory: Union[str, Path], pattern: str) -> List[Path]:
    """
    Recherche des fichiers correspondant à un motif dans un répertoire.

    Args:
        directory: Répertoire de recherche
        pattern: Motif de recherche (glob)

    Returns:
        List[Path]: Liste des chemins des fichiers trouvés
    """
    try:
        directory = Path(directory)
        return list(directory.glob(pattern))
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de fichiers dans {directory}: {e}")
        return []

def ensure_directory(directory: Union[str, Path]) -> bool:
    """
    Vérifie qu'un répertoire existe et le crée si nécessaire.

    Args:
        directory: Chemin du répertoire

    Returns:
        bool: True si le répertoire existe ou a été créé avec succès
    """
    try:
        directory = Path(directory)
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du répertoire {directory}: {e}")
        return False

def copy_file(source: Union[str, Path], destination: Union[str, Path]) -> bool:
    """
    Copie un fichier d'un emplacement à un autre.

    Args:
        source: Chemin source du fichier
        destination: Chemin de destination

    Returns:
        bool: True si la copie a réussi, False sinon
    """
    try:
        shutil.copy2(Path(source), Path(destination))
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la copie de {source} vers {destination}: {e}")
        return False

def get_file_size(file_path: Union[str, Path]) -> Optional[int]:
    """
    Retourne la taille d'un fichier en octets.

    Args:
        file_path: Chemin du fichier

    Returns:
        Optional[int]: Taille du fichier en octets, ou None si erreur
    """
    try:
        return Path(file_path).stat().st_size
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la taille du fichier {file_path}: {e}")
        return None