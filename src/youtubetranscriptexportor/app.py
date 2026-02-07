import asyncio

import nltk
import pyperclip
import toga
from pytubefix import extract
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from youtube_transcript_api import YouTubeTranscriptApi

from youtubetranscriptexportor.db import transcript

# Lazy load punctuation model to avoid startup errors
punct_model = None


def set_timeout(func, timeout=0.7, *args, **kwargs):
    async def wrapper():
        await asyncio.sleep(timeout)
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)

    return asyncio.create_task(wrapper())


def get_punct_model():
    """Lazy load the punctuation model."""
    global punct_model
    if punct_model is None:
        try:
            from deepmultilingualpunctuation import PunctuationModel

            punct_model = PunctuationModel(
                model="oliverguhr/fullstop-punctuation-multilang-large"
            )
        except Exception as e:
            print(f"Warning: Could not load punctuation model: {e}")
            punct_model = False  # Mark as failed
    return punct_model if punct_model is not False else None


nltk.download("punkt", quiet=True)


class YouTubeTranscriptApp(toga.App):
    def __init__(self):
        super().__init__(
            "YouTube Transcript Export",
            "org.example.yttranscript",
        )
        self.transcript_service = transcript.TranscriptService()
        self.is_always_on_top = False
        self.progress_bar = toga.ProgressBar(style=Pack(margin=1, height=0), max=100)
        self.ytt_api = YouTubeTranscriptApi()

    def startup(self):
        """Construct and show the Toga application."""
        self.show_progress()
        self.progress_bar.value = 0
        # Create main box
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))

        # Header section
        header_box = toga.Box(style=Pack(direction=ROW, margin=(0, 0, 10, 0)))
        title_label = toga.Label(
            "YouTube Transcript Export",
            style=Pack(margin=5, font_size=20, font_weight="bold", flex=1),
        )
        header_box.add(title_label)

        # Input section
        input_box = toga.Box(style=Pack(direction=ROW, margin=(10, 0)))
        self.progress_bar.value = 10

        self.url_input = toga.TextInput(
            placeholder="Paste your YouTube URL here",
            style=Pack(flex=1, margin=5),
            on_gain_focus=self.on_gain_focus,
        )

        self.paste_btn = toga.Button(
            "Paste", on_press=self.on_paste_clicked, style=Pack(margin=5, width=100)
        )

        self.save_btn = toga.Button(
            "Save", on_press=self.on_save_clicked, style=Pack(margin=5, width=100)
        )

        self.load_btn = toga.Button(
            "Load", on_press=self.on_load_clicked, style=Pack(margin=5, width=100)
        )
        self.load_btn.enabled = False

        input_box.add(self.url_input)
        input_box.add(self.paste_btn)
        input_box.add(self.save_btn)
        input_box.add(self.load_btn)
        self.progress_bar.value = 40

        # Divider (using a label as separator)
        divider = toga.Divider(style=Pack(margin=(5, 0)))

        # Result section
        self.text_result = toga.MultilineTextInput(
            placeholder="...",
            style=Pack(flex=1, margin=5, font_size=24),
            readonly=False,
        )

        # Status label for loading indication
        self.status_label = toga.Label(
            "",
            style=Pack(
                margin=(5, 2, 2, 2),
                font_size=8,
                font_style="italic",
                text_align="right",
                visibility="hidden",
            ),
        )

        # Add all components to main box
        main_box.add(header_box)
        main_box.add(input_box)
        main_box.add(divider)
        main_box.add(self.text_result)
        main_box.add(self.status_label)
        main_box.add(self.progress_bar)

        self.progress_bar.value = 60

        # Create main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.size = (700, 700)
        self.main_window.show()

        # Add keyboard shortcuts
        self.commands.add(
            toga.Command(
                self.on_save_clicked,
                "Save Transcript",
                shortcut=toga.Key.MOD_1 + "s",
                group=toga.Group.FILE,
            )
        )
        self.progress_bar.value = 80
        self.commands.add(
            toga.Command(
                self.toggle_always_on_top_mac,
                "Always on top",
                shortcut=toga.Key.MOD_1 + "t",
                group=toga.Group.WINDOW,
            )
        )

        self.progress_bar.value = 100
        set_timeout(self.hide_progress)

    def show_status(self, message, is_loading=False):
        """Update status label and hide after 5 seconds."""
        self.status_label.text = message
        self.status_label.style.visibility = "visible"

        # Cancel any existing clear task
        if hasattr(self, "_status_clear_task") and self._status_clear_task:
            self._status_clear_task.cancel()

        def clear():
            self.status_label.style.visibility = "hidden"
            self._status_clear_task = None

        self._status_clear_task = set_timeout(clear, 5)

    def enable_buttons(self, enabled=True):
        """Enable/disable buttons."""
        self.paste_btn.enabled = enabled
        self.save_btn.enabled = enabled

    def check_saved_transcript(self, video_id):
        """Check if transcript exists in database."""
        trans = self.transcript_service.get_transcript(video_id=video_id)
        if trans:
            self.load_btn.enabled = True
        return trans

    def _update_ui_with_transcript(self, result, success_message):
        """Update UI with transcript result."""
        self.text_result.value = result
        self.show_status(success_message)
        self.enable_buttons(True)

    def _update_ui_error(self, error_message):
        """Update UI with error."""
        self.show_status(f"Error: {error_message}", False)
        self.enable_buttons(True)
        toga.ErrorDialog("Error", error_message)

    async def fetch_transcript(self, video_id, should_reload=False):
        """Fetch transcript asynchronously."""
        # Update UI to show loading state
        self.show_status("Fetching transcript...", True)
        self.enable_buttons(False)

        loop = asyncio.get_running_loop()
        self.progress_bar.value = 30

        try:
            # Check if already saved (database operation, blocking)
            saved_trans = await loop.run_in_executor(
                None, self.transcript_service.get_transcript, video_id
            )
            self.progress_bar.value = 40

            if saved_trans and not should_reload:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                self.show_status('Transcript found in database. Click "Load" to view.')
                self.load_btn.enabled = True
                self.enable_buttons(True)
                return
            else:
                self.progress_bar.value = 50
                self.load_btn.enabled = False

            # Fetch from YouTube (network operation, blocking)
            # Define a helper for the complex logic
            def fetch_and_process():
                scr = self.ytt_api.fetch(video_id, languages=["en"])
                self.progress_bar.value = 70
                only_text = " ".join([s.text for s in scr])
                self.progress_bar.value = 72

                # Try to use punctuation model
                model = get_punct_model()
                self.progress_bar.value = 90
                if model:
                    txt = model.restore_punctuation(only_text)
                else:
                    txt = only_text

                sentences = nltk.tokenize.sent_tokenize(txt)
                return "\n".join(sentences)

            result = await loop.run_in_executor(None, fetch_and_process)
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            self._update_ui_with_transcript(result, "Transcript fetched successfully!")

        except Exception as err:
            print(f"Error fetching transcript: {err}")
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            error_msg = (
                str(err) if str(err) else "Video not found or transcript unavailable"
            )
            self._update_ui_error(error_msg)

    async def on_paste_clicked(self, widget):
        """Handle paste button click."""
        self.show_progress()
        self.progress_bar.value = 0
        try:
            # Get clipboard content
            clipboard_content = pyperclip.paste()
            self.progress_bar.value = 15
            self.url_input.value = clipboard_content

            # Extract video ID
            video_id = extract.video_id(clipboard_content)
            self.progress_bar.value = 25

            if not video_id:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                raise Exception("Invalid YouTube URL")

            # Fetch transcript
            await self.fetch_transcript(video_id, True)
            self.load_btn.enabled = True

        except Exception as err:
            print(f"Error: {err}")
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            toga.ErrorDialog("Error", str(err))

    async def on_gain_focus(self, widget):
        """Handle gain focus event."""
        self.show_progress()
        self.progress_bar.value = 0
        try:
            # Get clipboard content
            clipboard_content = pyperclip.paste()
            self.progress_bar.value = 15
            self.url_input.value = clipboard_content

            # Extract video ID
            video_id = extract.video_id(clipboard_content)
            self.progress_bar.value = 25

            if not video_id:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                # If invalid URL in clipboard, just ignore when focusing
                return

            # Fetch transcript
            await self.fetch_transcript(video_id)

        except Exception as err:
            # Silence errors on gain focus to avoid annoying popups
            print(f"Error on focus: {err}")
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)

    def on_save_clicked(self, widget):
        """Handle save button click."""
        self.show_progress()
        self.progress_bar.value = 0
        try:
            url = self.url_input.value
            if not url:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                toga.ErrorDialog("Error", "Please enter a YouTube URL")
                return
            self.progress_bar.value = 5

            video_id = extract.video_id(url)
            if not video_id:
                raise Exception("Invalid YouTube URL")
            self.progress_bar.value = 20

            transcript_text = self.text_result.value
            if not transcript_text:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                toga.ErrorDialog("Error", "No transcript to save")
                return

            self.transcript_service.upsert(
                video_id=video_id, transcript=transcript_text
            )
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            self.show_status("Transcript saved successfully!")
            self.load_btn.enabled = True

        except Exception as err:
            print(f"Error saving: {err}")
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            toga.ErrorDialog("Error", f"Failed to save: {err}")

    def on_load_clicked(self, widget):
        """Handle load button click."""
        self.show_progress()
        self.progress_bar.value = 0
        try:
            url = self.url_input.value
            if not url:
                set_timeout(self.hide_progress)
                toga.ErrorDialog("Error", "Please enter a YouTube URL")
                return

            video_id = extract.video_id(url)
            if not video_id:
                raise Exception("Invalid YouTube URL")
            self.progress_bar.value = 20

            saved_transcript = self.transcript_service.get_transcript(video_id=video_id)
            self.progress_bar.value = 60

            if saved_transcript:
                self.text_result.value = saved_transcript
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                self.show_status("Transcript loaded from database")
            else:
                self.progress_bar.value = 100
                set_timeout(self.hide_progress)
                toga.ErrorDialog("Error", "No saved transcript found for this video")

        except Exception as err:
            print(f"Error loading: {err}")
            self.progress_bar.value = 100
            set_timeout(self.hide_progress)
            toga.ErrorDialog("Error", f"Failed to load: {err}")

    def toggle_always_on_top_mac(self, widget):
        ns_window = self.main_window._impl.native  # NSWindow
        NSFloatingWindowLevel = 3
        NSNormalWindowLevel = 0

        if self.is_always_on_top:
            ns_window.setLevel_(NSFloatingWindowLevel)
        else:
            ns_window.setLevel_(NSNormalWindowLevel)
        self.is_always_on_top = not self.is_always_on_top

    def hide_progress(self):
        self.progress_bar.style.visibility = "hidden"
        self.progress_bar.value = 0
        self.progress_bar.stop()

    def show_progress(self):
        self.progress_bar.style.visibility = "visible"
        self.progress_bar.start()


def main():
    return YouTubeTranscriptApp()


if __name__ == "__main__":
    main().main_loop()
