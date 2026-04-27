"""
Менеджер сессий для многопользовательской работы
"""
import threading
import asyncio
from typing import Dict, Optional
from core.logger import logger
import bot.utils.helpers as tb_helpers


class SessionManager:
    def __init__(self):
        self._sessions: Dict[int, threading.Thread] = {}
        self._auth_sessions: Dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

    def start_auth_session(self, telegram_id: int) -> bool:
        with self._lock:
            if telegram_id in self._auth_sessions and self._auth_sessions[telegram_id].is_alive():
                logger.warning(f"Авторизация для {telegram_id} уже запущена")
                return False
            thread = threading.Thread(
                target=self._run_auth_session,
                args=(telegram_id,),
                daemon=True
            )
            self._auth_sessions[telegram_id] = thread
            thread.start()
            logger.info(f"Авторизация для {telegram_id} запущена")
            return True

    def _run_auth_session(self, telegram_id: int):
        import time
        from core.browser import launch_browser
        from services.hh_auth import login_to_hh

        try:
            with launch_browser(telegram_id=telegram_id) as page:
                asyncio.run_coroutine_threadsafe(
                    tb_helpers.telegram_bot.send_message(
                        telegram_id,
                        "🌐 Браузер открыт!\n\n"
                        "📱 Введи номер телефона (10 цифр без +7 и 8):\n"
                        "Пример: `9060295956`"
                    ),
                    tb_helpers.telegram_loop
                )

                tb_helpers.auth_events[telegram_id] = threading.Event()
                tb_helpers.auth_data[telegram_id] = {}
                tb_helpers.auth_events[telegram_id].wait(timeout=120)

                phone = tb_helpers.auth_data[telegram_id].get('phone')
                if not phone:
                    asyncio.run_coroutine_threadsafe(
                        tb_helpers.telegram_bot.send_message(telegram_id, "❌ Таймаут. Попробуй снова."),
                        tb_helpers.telegram_loop
                    )
                    return

                tb_helpers.auth_events[telegram_id].clear()

                def sms_code_getter():
                    asyncio.run_coroutine_threadsafe(
                        tb_helpers.telegram_bot.send_message(
                            telegram_id,
                            "📨 Номер введён! Жди SMS от hh.ru.\n\nВведи код из SMS:"
                        ),
                        tb_helpers.telegram_loop
                    )
                    tb_helpers.auth_events[telegram_id].wait(timeout=120)
                    return tb_helpers.auth_data[telegram_id].get('sms_code')

                success = login_to_hh(page, phone, sms_code_getter)

                if success:
                    asyncio.run_coroutine_threadsafe(
                        tb_helpers.telegram_bot.send_message(
                            telegram_id,
                            "✅ Авторизация успешна! Сессия сохранена.\n\nТеперь можешь запускать отклики!"
                        ),
                        tb_helpers.telegram_loop
                    )
                else:
                    asyncio.run_coroutine_threadsafe(
                        tb_helpers.telegram_bot.send_message(telegram_id, "❌ Авторизация не удалась. Попробуй снова."),
                        tb_helpers.telegram_loop
                    )

        except Exception as e:
            logger.exception(f"Ошибка авторизации для {telegram_id}: {e}")
            asyncio.run_coroutine_threadsafe(
                tb_helpers.telegram_bot.send_message(telegram_id, f"❌ Ошибка: {e}"),
                tb_helpers.telegram_loop
            )
        finally:
            with self._lock:
                if telegram_id in self._auth_sessions:
                    del self._auth_sessions[telegram_id]
            tb_helpers.auth_events.pop(telegram_id, None)
            tb_helpers.auth_data.pop(telegram_id, None)

    def start_session(self, telegram_id: int, job_title: str, limit: int, custom_url: str = None) -> bool:
        with self._lock:
            if telegram_id in self._sessions and self._sessions[telegram_id].is_alive():
                logger.warning(f"Сессия для {telegram_id} уже активна")
                return False
            thread = threading.Thread(
                target=self._run_hh_session,
                args=(telegram_id, job_title, limit, custom_url),
                daemon=True
            )
            self._sessions[telegram_id] = thread
            thread.start()
            logger.info(f"Сессия для {telegram_id} запущена")
            return True

    def stop_session(self, telegram_id: int):
        with self._lock:
            if telegram_id in self._sessions:
                tb_helpers.user_stop_flags[telegram_id] = True
                logger.info(f"Отправлен сигнал остановки для {telegram_id}")
            else:
                logger.warning(f"Нет активной сессии для {telegram_id}")

    def is_session_running(self, telegram_id: int) -> bool:
        with self._lock:
            thread = self._sessions.get(telegram_id)
            return thread is not None and thread.is_alive()

    def _run_hh_session(self, telegram_id: int, job_title: str, limit: int, custom_url: str = None):
        import time
        import random
        from urllib.parse import quote
        from core.browser import launch_browser
        from core.ai_client import get_ai_client
        from services.hh_parser import collect_vacancies_from_url, get_vacancy_description
        from services.applier import apply_to_vacancy
        from services.letter_generator import LetterGenerator
        from services.revaz_agent import RevazAgent
        from services.alina_validator import AlinaValidator
        from storage.history_repository import add_application, get_applied_ids
        from storage.database import SyncDatabase

        tb_helpers.user_sessions_active[telegram_id] = True
        tb_helpers.user_stop_flags[telegram_id] = False

        try:
            user = SyncDatabase.get_user(telegram_id)
            if not user:
                logger.error(f"Пользователь {telegram_id} не найден")
                return
            resume = SyncDatabase.get_active_resume(telegram_id)
            if not resume:
                logger.error(f"У пользователя {telegram_id} нет активного резюме")
                return

            settings = user.get('settings', {})
            manual = settings.get('manual_mode', False)
            tb_helpers.user_manual_mode[telegram_id] = manual

            if custom_url:
                search_url = custom_url
            else:
                search_query = quote(job_title)
                search_url = f"https://hh.ru/search/vacancy?text={search_query}&area=1"

            ai_client = get_ai_client()
            letter_gen = LetterGenerator()
            revaz = RevazAgent(resume)
            alina = AlinaValidator()
            applied_ids = get_applied_ids(telegram_id)
            total_applies = 0

            with launch_browser(telegram_id=telegram_id) as page:
                tb_helpers.set_global_page(page)
                tb_helpers.set_global_ai_client(ai_client)
                tb_helpers.set_global_resume(resume)

                time.sleep(random.uniform(2, 5))
                max_pages = max(1, (limit - 1) // 50 + 1)
                vacancies = collect_vacancies_from_url(page, search_url, telegram_id, chat_id=telegram_id, max_pages=max_pages)
                if not vacancies:
                    logger.warning("Вакансий не найдено")
                    return

                for vac in vacancies[:limit]:
                    if tb_helpers.user_stop_flags.get(telegram_id, False):
                        break
                    if vac['id'] in applied_ids:
                        continue

                    logger.info(f"🎯 {vac['title'][:50]}")
                    try:
                        vac_text, salary, company, area = get_vacancy_description(page, vac['url'])
                        if salary != 'Не указана':
                            vac['salary'] = salary
                        if company != 'Не указана':
                            vac['company'] = company
                        if area != 'Не указан':
                            vac['area'] = area
                        if not vac_text:
                            vac_text = ""

                        passed, reason, revaz_score = revaz.check(vac, vac_text)

                        if not passed and not manual:
                            add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'revaz_skip', error=reason)
                            continue

                        letter = letter_gen.generate(resume, vac_text, vac['title'])
                        vac['company'] = vac.get('company', 'Не указана')
                        vac['salary'] = vac.get('salary', 'Не указана')
                        vac['area'] = vac.get('area', 'Не указан')

                        if manual:
                            logger.info(f"🟡 Ручной режим: {vac['title'][:40]}")
                            tb_helpers.manual_decisions.pop(vac['id'], None)
                            tb_helpers.get_user_decision_event(telegram_id).clear()

                            if tb_helpers.telegram_loop:
                                asyncio.run_coroutine_threadsafe(
                                    tb_helpers.send_vacancy_card(telegram_id, vac, letter, revaz_score, reason),
                                    tb_helpers.telegram_loop
                                )
                            else:
                                continue

                            decision = None
                            start_wait = time.time()
                            event = tb_helpers.user_decision_events[telegram_id]
                            while time.time() - start_wait < 120:
                                if event.wait(timeout=1):
                                    decision = tb_helpers.manual_decisions.get(vac['id'])
                                    break
                                if tb_helpers.user_stop_flags.get(telegram_id, False):
                                    break

                            if decision == "apply":
                                success = apply_to_vacancy(page, vac, letter, resume, ai_client)
                                if success:
                                    total_applies += 1
                                    add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'sent', letter)
                                else:
                                    add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'error', letter, error="отправка не удалась")
                            elif decision == "skip":
                                add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'skipped', letter)
                            elif decision == "regen":
                                new_letter = letter_gen.generate(resume, vac_text, vac['title'])
                                new_letter = alina.validate_and_improve(new_letter, resume, vac_text, vac['title'])
                                tb_helpers.manual_decisions.pop(vac['id'], None)
                                event.clear()
                                if tb_helpers.telegram_loop:
                                    asyncio.run_coroutine_threadsafe(
                                        tb_helpers.send_vacancy_card(telegram_id, vac, new_letter, revaz_score, reason),
                                        tb_helpers.telegram_loop
                                    )
                                start_wait2 = time.time()
                                while time.time() - start_wait2 < 120:
                                    if event.wait(timeout=1):
                                        decision = tb_helpers.manual_decisions.get(vac['id'])
                                        break
                                if decision == "apply":
                                    success = apply_to_vacancy(page, vac, new_letter, resume, ai_client)
                                    if success:
                                        total_applies += 1
                                        add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'sent', new_letter)
                                elif decision == "skip":
                                    add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'skipped', new_letter)
                            else:
                                add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'skipped', letter, error="timeout")
                            continue

                        # Автоматический режим — передаём скор
                        success = apply_to_vacancy(page, vac, letter, resume, ai_client)
                        if success:
                            total_applies += 1
                            add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'sent', letter)
                            if tb_helpers.telegram_loop:
                                asyncio.run_coroutine_threadsafe(
                                    tb_helpers.send_auto_apply_card(telegram_id, vac, letter, revaz_score, reason),
                                    tb_helpers.telegram_loop
                                )
                        else:
                            add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'error', letter, error="отправка не удалась")

                    except Exception as e:
                        logger.exception(f"Ошибка при вакансии '{vac['id']}': {e}")
                        add_application(telegram_id, vac['id'], vac['title'], vac['url'], 'error', error=str(e))
                        continue

                    time.sleep(random.uniform(5, 10))

        except Exception as e:
            logger.exception(f"Критическая ошибка в сессии {telegram_id}: {e}")
        finally:
            tb_helpers.user_sessions_active[telegram_id] = False
            tb_helpers.user_stop_flags.pop(telegram_id, None)
            tb_helpers.user_manual_mode.pop(telegram_id, None)
            with self._lock:
                if telegram_id in self._sessions:
                    del self._sessions[telegram_id]
            logger.info(f"Сессия для {telegram_id} завершена, отправлено {total_applies}")


session_manager = SessionManager()