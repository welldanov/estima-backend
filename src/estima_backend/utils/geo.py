import numpy as np

EARTH_RADIUS_KM = 6371.0


def calculate_distance_km(
        *,
        lat1: float | np.ndarray,
        lon1: float | np.ndarray,
        lat2: float | np.ndarray,
        lon2: float | np.ndarray,
) -> float | np.ndarray:
    # Формула гаверсинусов. Работает и для чисел, и поэлементно
    # для массивов/pd.Series: признаки считаются для всего датасета сразу.
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)

    delta_lat = np.radians(lat2 - lat1)
    delta_lon = np.radians(lon2 - lon1)

    a = (
            np.sin(delta_lat / 2) ** 2
            + np.cos(lat1_rad)
            * np.cos(lat2_rad)
            * np.sin(delta_lon / 2) ** 2
    )

    c = 2 * np.arctan2(
        np.sqrt(a),
        np.sqrt(1 - a),
    )

    return EARTH_RADIUS_KM * c
