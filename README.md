# 🍽️ Sorteo de Comidas

Una aplicación web para organizar automáticamente a las personas en grupos de comidas y cenas de forma balanceada.

## ✨ Características

- 🎲 Sorteo aleatorio pero balanceado
- 📊 Distribución equitativa entre grupos
- 🍽️ Prioriza que las cenas tengan menos personas
- 🔧 Configuración flexible de participantes
- 🌐 Interfaz web fácil de usar

## 🚀 Uso

### En la web
Visita la aplicación desplegada en Streamlit Cloud: [enlace pendiente]

### Local
```bash
pip install streamlit
streamlit run app.py
```

## 📝 Formato de entrada

```
TODO:
- Persona que puede ir a cualquier grupo
- Otra persona flexible

- Comida 9
- Persona específica para comida del día 9
- Otra persona para comida del día 9

- Cena 9
- Persona específica para cena del día 9

- Comida 10
- Persona para comida del día 10
```

## 🎯 Algoritmo

El algoritmo:
1. Prioriza personas con menos opciones de grupo
2. Balancea los tamaños entre grupos
3. Prefiere comidas sobre cenas para mantener cenas más pequeñas
4. Garantiza que todos tengan asignación válida