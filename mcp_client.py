# -*- coding: utf-8 -*-
"""
mcp_client.py: Демонстрационный MCP клиент с интеграцией OpenAI

Этот скрипт подключается к локальному MCP серверу, получает список
доступных инструментов и использует OpenAI API (функция chat completions
с tools) для определения, какой MCP инструмент вызвать для ответа
на запрос пользователя в интерактивном режиме чата.
"""

# %% [markdown]
# ## 1. Импорты
#
# Добавляем `openai`, `os` (для API ключа) и `json` (для парсинга аргументов).
# Добавляем `load_dotenv` для чтения файла `.env`.

# %%
import asyncio
import os
import json
from openai import AsyncOpenAI # Используем асинхронного клиента
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp.types as types
from dotenv import load_dotenv # Добавляем импорт

# Загружаем переменные из .env файла (если он есть)
# Это нужно сделать до первого обращения к os.environ
load_dotenv()
print("[Client Setup] Попытка загрузки переменных из .env")

# %% [markdown]
# ## 2. Функция для преобразования MCP Tool в формат OpenAI Tool
#
# OpenAI API ожидает описание инструментов в своем формате. Эта функция
# конвертирует описание инструмента, полученное от MCP сервера,
# в формат, понятный OpenAI.

# %%
def mcp_tool_to_openai_tool(mcp_tool: types.Tool) -> dict:
    """Конвертирует MCP Tool в формат OpenAI Tool Function."""
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # Безопасно получаем атрибут 'arguments', используя getattr. Возвращаем None, если его нет.
    mcp_arguments = getattr(mcp_tool, 'arguments', None)

    if mcp_arguments: # Проверяем, что список аргументов существует и не пуст
        for arg in mcp_arguments:
            # OpenAI ожидает описание параметров в формате JSON Schema.
            # Мы делаем простое предположение, что все аргументы - строки.
            # Также безопасно получаем атрибуты самого аргумента (name, description, required)
            arg_name = getattr(arg, 'name', None)
            if not arg_name:
                print(f"[Warning] MCP Tool Argument в {mcp_tool.name} не имеет имени, пропуск.")
                continue # Пропускаем аргумент без имени

            arg_description = getattr(arg, 'description', '') or '' # Описание может быть None
            arg_required = getattr(arg, 'required', False)

            parameters["properties"][arg_name] = {
                "type": "string", # TODO: В идеале тип должен приходить от MCP
                "description": arg_description,
            }
            if arg_required:
                parameters["required"].append(arg_name)

    tool_name = getattr(mcp_tool, 'name', 'unknown_tool')
    tool_description = getattr(mcp_tool, 'description', '') or ''

    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": parameters,
        },
    }

# %% [markdown]
# ## 3. Основная асинхронная функция `run_client`
#
# Модифицируем эту функцию для использования OpenAI и добавления режима чата.

# %%
async def run_client():
    """
    Основная асинхронная функция для запуска клиента, взаимодействия с MCP сервером
    и использования OpenAI для вызова инструментов в режиме чата.
    """
    print("[Client] Запуск MCP клиента с интеграцией OpenAI в режиме чата...")

    # %% [markdown]
    # ### 3.1 Настройка клиента OpenAI
    # Создаем асинхронного клиента OpenAI. API ключ должен быть установлен
    # в переменной окружения `OPENAI_API_KEY`.
    # %%
    print("[Client] Настройка клиента OpenAI...")
    try:
        openai_client = AsyncOpenAI()
        if not openai_client.api_key:
            raise ValueError("Переменная окружения OPENAI_API_KEY не установлена.")
        print("[Client] Клиент OpenAI настроен.")
    except Exception as e:
        print(f"[Client] Ошибка настройки клиента OpenAI: {e}")
        print("[Client] Убедитесь, что библиотека openai установлена (`pip install openai`)")
        print("[Client] и переменная окружения OPENAI_API_KEY установлена.")
        return # Выход, если клиент не настроен

    # %% [markdown]
    # ### 3.2 Параметры запуска MCP сервера
    # Указываем, как запустить наш локальный `mcp_server.py`.
    # %%
    print("[Client] Настройка параметров запуска MCP сервера (StdioServerParameters)...")
    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_server.py"],
    )
    print(f"[Client] Параметры: command='{server_params.command}', args={server_params.args}")

    # %% [markdown]
    # ### 3.3 Установка соединения с MCP сервером и подготовка к чату
    # Соединяемся с сервером, получаем инструменты и инициализируем историю чата.
    # %%
    print("[Client] Попытка запуска MCP сервера и установки соединения через stdio_client...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        print("[Client] Соединение с MCP сервером установлено.")

        print("[Client] Создание ClientSession...")
        async with ClientSession(read_stream, write_stream) as session:
            print("[Client] ClientSession создана.")

            # #### 3.3.1 Инициализация MCP и получение инструментов ####
            print("[Client] Инициализация MCP...")
            init_response = await session.initialize()
            print(f"[Client] Сервер инициализирован: {init_response.serverInfo.name} v{init_response.serverInfo.version}")

            print("[Client] Запрос списка инструментов у MCP сервера...")
            openai_tools = [] # Инициализируем пустым списком
            try:
                list_tools_result = await session.list_tools()
                mcp_tools_list = list_tools_result.tools
                if not mcp_tools_list:
                     print("[Client] Сервер не предоставил инструментов. Работаем без них.")
                else:
                    print(f"[Client] Получено {len(mcp_tools_list)} инструментов от MCP сервера.")
                    openai_tools = [mcp_tool_to_openai_tool(tool) for tool in mcp_tools_list]
                    print("[Client] Инструменты сконвертированы в формат OpenAI.")
            except Exception as e:
                print(f"[Client] Ошибка при получении или конвертации инструментов: {e}. Работаем без них.")

            # #### 3.3.2 Инициализация истории чата ####
            messages = [
                {"role": "system", "content": """Ты полезный русскоязычный ассистент-калькулятор. У тебя есть доступ к следующим математическим инструментам:
1. add - сложение двух чисел
2. subtract - вычитание двух чисел

Когда пользователь просит произвести математические вычисления:
- Используй add для сложения
- Используй subtract для вычитания


Всегда используй инструменты для вычислений, даже для простых операций."""}
            ]
            print("\n" + "="*25 + " Начат Чат с Ассистентом " + "="*25)
            print('Введите ваш запрос или "выход" для завершения.')
#- Для других математических операций - говори, что не можешь выполнить.

            # %% [markdown]
            # ### 3.4 Цикл чата
            # Бесконечный цикл для приема запросов пользователя и взаимодействия с OpenAI/MCP.
            # %%
            while True:
                try:
                    # --- Получение ввода пользователя ---
                    user_request = input("\nВы: ")
                    if user_request.strip().lower() == "выход":
                        print("[Client] Завершение чата по команде пользователя.")
                        break
                    if not user_request.strip():
                        continue # Пропускаем пустой ввод

                    # Добавляем сообщение пользователя в историю
                    messages.append({"role": "user", "content": user_request})

                    # --- Взаимодействие с OpenAI ---
                    print("[Client] Отправка запроса и истории в OpenAI...")
                    response = await openai_client.chat.completions.create(
                        model="gpt-4o", # Или gpt-3.5-turbo
                        messages=messages,
                        tools=openai_tools if openai_tools else None, # Передаем None если список пуст
                        tool_choice="auto",
                    )
                    response_message = response.choices[0].message
                    tool_calls = response_message.tool_calls

                    # --- Обработка ответа OpenAI (Вызов инструментов или прямой ответ) ---
                    if tool_calls:
                        print(f"[Client] OpenAI решила вызвать инструмент(ы): {[call.function.name for call in tool_calls]}")
                        # Добавляем намерение ассистента вызвать инструмент в историю
                        # Важно: добавляем объект сообщения как есть
                        messages.append(response_message)

                        tool_results_messages = [] # Собираем результаты для второго вызова
                        for tool_call in tool_calls:
                            function_name = tool_call.function.name
                            tool_call_id = tool_call.id
                            print(f"[Client] -> Обработка вызова инструмента: {function_name}")
                            try:
                                function_args = json.loads(tool_call.function.arguments)
                                print(f"[Client]    Аргументы от OpenAI: {function_args}")
                                print(f"[Client]    Вызов {function_name} на MCP сервере...")
                                mcp_tool_result = await session.call_tool(function_name, arguments=function_args)
                                print(f"[Client]    Результат от MCP сервера: {mcp_tool_result}")
                                tool_results_messages.append({"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": str(mcp_tool_result)})
                            except json.JSONDecodeError as e:
                                print(f"[Client]    Ошибка: Не удалось распарсить аргументы JSON: {tool_call.function.arguments}, {e}")
                                tool_results_messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": function_name, "content": "Ошибка: неверный формат аргументов JSON."})
                            except Exception as e:
                                print(f"[Client]    Ошибка при вызове MCP инструмента {function_name}: {e}")
                                tool_results_messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": function_name, "content": f"Ошибка выполнения инструмента: {e}"})

                        # Добавляем все результаты инструментов в историю
                        messages.extend(tool_results_messages)

                        # Получаем финальный ответ от OpenAI после вызова инструментов
                        print("[Client] Отправка результатов инструментов обратно в OpenAI...")
                        second_response = await openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            # tools и tool_choice здесь не нужны, т.к. мы ждем текстовый ответ
                        )
                        final_answer = second_response.choices[0].message.content
                        # Добавляем финальный ответ ассистента в историю
                        messages.append({"role": "assistant", "content": final_answer})

                    else:
                        # OpenAI ответила сразу без инструментов
                        final_answer = response_message.content
                        # Добавляем ответ ассистента в историю
                        messages.append({"role": "assistant", "content": final_answer})

                    # --- Вывод ответа пользователю ---
                    print(f"\nАссистент: {final_answer}")

                except Exception as e:
                    print(f"\n[Client] Произошла ошибка в цикле чата: {e}")
                    break 

            # --- Конец цикла чата ---
            print("\n" + "="*28 + " Чат Завершен " + "="*28)

        print("[Client] ClientSession закрыта.")
    print("[Client] Соединение с MCP сервером закрыто.")


# %% [markdown]
# ## 4. Точка входа
# Запускаем `run_client` при исполнении скрипта.
# %%
if __name__ == "__main__":
    print("[Client Main] Скрипт запущен напрямую.")
    # Проверка наличия ключа перед запуском основного кода
    if "OPENAI_API_KEY" not in os.environ:
         print("[Client Main] ОШИБКА: Переменная окружения OPENAI_API_KEY не найдена.")
         print("[Client Main] Пожалуйста, установите её перед запуском скрипта.")
         print("[Client Main] Пример: export OPENAI_API_KEY='ваш_ключ'")
    else:
        try:
            asyncio.run(run_client())
            print("[Client Main] asyncio.run завершен.")
        except KeyboardInterrupt:
            print("\n[Client Main] Выполнение прервано пользователем (KeyboardInterrupt).")
        except Exception as e:
             print(f"[Client Main] Непредвиденная ошибка: {e}")

""" End of mcp_client.py """
