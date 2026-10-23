"""
Capa de servicios para la gestión de anuncios.
Contiene la lógica de negocio para la creación, obtención, actualización y eliminación de anuncios.
"""

from backend.app.datos import ads as datos_ads


def crear_anuncio(usuario_id: int, categoria_id: int, titulo: str, descripcion: str,
                  precio_centavos: int) -> int:
    """
    Crea un nuevo anuncio después de validar los datos.
    
    Args:
        usuario_id: ID del usuario dueño del anuncio
        categoria_id: ID de la categoría del anuncio
        titulo: Título del anuncio
        descripcion: Descripción del anuncio
        precio_centavos: Precio en centavos
        
    Returns:
        ID del nuevo anuncio creado
        
    Raises:
        ValueError: Si los datos no son válidos
    """
    # Validación de datos
    if not titulo:
        raise ValueError("Título no puede estar vacío")
    
    if not descripcion:
        raise ValueError("Descripción no puede estar vacía")
        
    if not isinstance(precio_centavos, int):
        raise ValueError("Precio debe ser un número entero")
        
    if precio_centavos < 0:
        raise ValueError("Precio no puede ser negativo")
    
    # Delegación a la capa de datos
    return datos_ads.insert_ad(usuario_id, categoria_id, titulo, descripcion, precio_centavos)


def obtener_anuncio(ad_id: int) -> dict | None:
    """
    Obtiene un anuncio por su ID.
    
    Args:
        ad_id: ID del anuncio a obtener
        
    Returns:
        Diccionario con los datos del anuncio o None si no existe
    """
    return datos_ads.get_ad_by_id(ad_id)


def actualizar_anuncio(ad_id: int, usuario_id: int, titulo: str, descripcion: str,
                       precio_centavos: int) -> bool:
    """
    Actualiza un anuncio después de validar los datos y verificar que el usuario sea el dueño.
    
    Args:
        ad_id: ID del anuncio a actualizar
        usuario_id: ID del usuario que intenta actualizar
        titulo: Nuevo título del anuncio
        descripcion: Nueva descripción del anuncio
        precio_centavos: Nuevo precio en centavos
        
    Returns:
        True si la actualización fue exitosa, False si no se encontró el anuncio
    """
    # Validación de datos
    if not titulo:
        raise ValueError("Título no puede estar vacío")
    
    if not descripcion:
        raise ValueError("Descripción no puede estar vacía")
        
    if not isinstance(precio_centavos, int):
        raise ValueError("Precio debe ser un número entero")
        
    if precio_centavos < 0:
        raise ValueError("Precio no puede ser negativo")
    
    # Delegación a la capa de datos
    return datos_ads.update_ad(ad_id, usuario_id, titulo, descripcion, precio_centavos)


def eliminar_anuncio(ad_id: int, usuario_id: int) -> bool:
    """
    Elimina un anuncio después de verificar que el usuario sea el dueño.
    
    Args:
        ad_id: ID del anuncio a eliminar
        usuario_id: ID del usuario que intenta eliminar
        
    Returns:
        True si la eliminación fue exitosa, False si no se encontró el anuncio
    """
    # Delegación a la capa de datos
    return datos_ads.delete_ad(ad_id, usuario_id)