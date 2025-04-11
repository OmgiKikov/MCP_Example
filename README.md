# MCP Calculator Example

Демонстрационный проект, показывающий работу с Model Context Protocol (MCP).

## Описание

Проект состоит из двух основных компонентов:
1. MCP сервер (`mcp_server.py`) - предоставляет математические операции:
   - Сложение (add)
   - Вычитание (subtract)
   - Умножение (multiply)

2. MCP клиент (`mcp_client.py`) - взаимодействует с сервером через OpenAI API

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/OmgiKikov/MCP_Example.git
cd MCP_Example
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` и добавьте ваш OpenAI API ключ:
```bash
OPENAI_API_KEY=your_api_key_here
```

## Использование

1. Запустите клиент:
```bash
python mcp_client.py
```

2. Введите математические выражения в чате, например:
- "сложи 5 и 3"
- "вычти из 10 число 4"
- "умножь 6 на 7"

## Требования

- Python 3.8+
- OpenAI API ключ
- Установленные зависимости из requirements.txt 