# Ejecutar el proyecto

## 1. Instala todas las dependencias

Dependencias utilizadas:

- **fastapi**: Framework web utilizado para construir la API REST.
- **uvicorn**: Servidor ASGI necesario para correr y desplegar la aplicación de FastAPI.
- **pydantic**: Utilizado para la validación de datos y la creación de esquemas (`BaseModel`) en los endpoints de la API.

### Windows
```bash
pip install fastapi uvicorn pydantic
```

### Linux / macOS
```bash
pip3 install fastapi uvicorn pydantic
```

---

## 2. Crea el entorno virtual

### Windows
```bash
python -m venv venv
```

### Linux / macOS
```bash
python3 -m venv venv
```

---

## 3. Activa el entorno virtual

### Windows
```bash
venv\Scripts\activate
```

### Linux / macOS
```bash
source venv/bin/activate
```

---

## 4. Corre el servidor

```bash
uvicorn server:app --reload --port 8000
```

---

## 5. Abre el proyecto

Abre el siguiente enlace en tu navegador:

```text
http://localhost:8000
```
O accede dando ```Ctrl + click``` sobre el link en tu terminal


Para desactivar el entorno virtual utiliza:

```bash
deactivate
```

---

## Nota

Si algún comando `python` o `pip` no funciona, intenta utilizar:

- `python3`
- `pip3`

dependiendo de tu sistema operativo.
