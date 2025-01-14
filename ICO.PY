import os
import json
import shutil
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PIL import Image
from io import BytesIO

# ملف الإعدادات
settings_file = "settings.json"

# تحميل الإعدادات
def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r") as file:
            settings = json.load(file)
    else:
        settings = {}

    settings.setdefault("main_path", "")
    settings.setdefault("original_folder", "")
    settings.setdefault("supported_formats", "jpg,jpeg,png,gif,bmp,tiff,webp")
    settings.setdefault("possible_icons", "Poster.ico,poster.ico,cover.ico,folder.ico")
    settings.setdefault("default_icon", "")
    settings.setdefault("use_default_icon", 1)  # افتراضيًا، الأيقونة الافتراضية مفعلة
    settings.setdefault("archive_folder", "")  # إضافة مجلد الأرشيف إلى الإعدادات
    settings.setdefault("subfolder_levels", 2)  # عدد التفرعات الافتراضي

    return settings

# حفظ الإعدادات
def save_settings(settings):
    with open(settings_file, "w") as file:
        json.dump(settings, file)

class HideUnhideThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, folder_path, action):
        super().__init__()
        self.folder_path = folder_path
        self.action = action  # "hide" أو "unhide"

    def run(self):
        try:
            folders = []
            for root, _, _ in os.walk(self.folder_path):
                folders.append(root)

            total_folders = len(folders)
            for i, root in enumerate(folders):
                # إخفاء أو إظهار desktop.ini
                ini_path = os.path.join(root, "desktop.ini")
                if os.path.exists(ini_path):
                    if self.action == "hide":
                        os.system(f'attrib +h +s "{ini_path}"')  # إخفاء أقوى
                    elif self.action == "unhide":
                        os.system(f'attrib +h -s "{ini_path}"')  # إظهار

                # إخفاء أو إظهار الأيقونة
                icon_path = os.path.join(root, "Poster.ico")
                if os.path.exists(icon_path):
                    if self.action == "hide":
                        os.system(f'attrib +h +s "{icon_path}"')  # إخفاء أقوى
                    elif self.action == "unhide":
                        os.system(f'attrib -h -s "{icon_path}"')  # إظهار

                self.progress.emit(int((i + 1) / total_folders * 100))  # تحديث شريط التقدم

            self.finished.emit(f"تم {self.action} الملفات والأيقونات بنجاح!")
        except Exception as e:
            self.finished.emit(f"حدث خطأ أثناء العملية: {e}")

class ConversionThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, input_folder, original_folder, supported_formats):
        super().__init__()
        self.input_folder = input_folder
        self.original_folder = original_folder
        self.supported_formats = supported_formats

    def run(self):
        try:
            os.makedirs(self.original_folder, exist_ok=True)
            files = []
            for root, _, filenames in os.walk(self.input_folder):
                for filename in filenames:
                    if filename.lower().endswith(self.supported_formats):
                        files.append((root, filename))

            total_files = len(files)
            for i, (root, filename) in enumerate(files):
                input_path = os.path.join(root, filename)
                relative_folder = os.path.relpath(root, self.input_folder)
                original_subfolder_path = os.path.join(self.original_folder, relative_folder)
                os.makedirs(original_subfolder_path, exist_ok=True)
                original_path = os.path.join(original_subfolder_path, filename)

                img = Image.open(input_path)
                img = img.convert("RGBA")
                max_size = max(img.size)
                square_canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
                offset = ((max_size - img.size[0]) // 2, (max_size - img.size[1]) // 2)
                square_canvas.paste(img, offset)

                output_path = os.path.join(root, "Poster.ico")
                icon_sizes = [(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
                square_canvas.save(output_path, format="ICO", sizes=icon_sizes)

                # نقل الصورة الأصلية إلى مجلد النسخ الاحتياطي
                shutil.move(input_path, original_path)

                # إنشاء أو استبدال ملف desktop.ini للمجلد الحالي
                ini_path = os.path.join(root, "desktop.ini")

                # إذا كان الملف موجودًا، يتم حذفه
                if os.path.exists(ini_path):
                    os.remove(ini_path)

                # إنشاء محتوى ملف desktop.ini
                ini_content = f"""[.ShellClassInfo]
IconResource=Poster.ico,0"""

                # كتابة محتوى ملف desktop.ini
                with open(ini_path, "w") as ini_file:
                    ini_file.write(ini_content)

                # جعل ملف desktop.ini مخفيًا والمجلد نظاميًا
                os.system(f'attrib +h "{ini_path}"')
                os.system(f'attrib +s "{root}"')
                os.system(f'attrib +r "{root}"')

                print(f"تم تحويل {filename} إلى أيقونة وحفظها في: {output_path}")
                print(f"تم إنشاء أو استبدال ملف desktop.ini في: {root}")

                self.progress.emit(int((i + 1) / total_files * 100))  # تحديث شريط التقدم

            self.finished.emit("تمت عملية التحويل بنجاح!")
        except Exception as e:
            self.finished.emit(f"حدث خطأ أثناء العملية: {e}")

class DesktopIniThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, folder_path, possible_icons, default_icon, use_default_icon):
        super().__init__()
        self.folder_path = folder_path
        self.possible_icons = possible_icons
        self.default_icon = default_icon
        self.use_default_icon = use_default_icon

    def run(self):
        try:
            folders = []
            for root, _, _ in os.walk(self.folder_path):
                folders.append(root)

            total_folders = len(folders)
            for i, root in enumerate(folders):
                icon_name = None
                for icon in self.possible_icons:
                    icon_path = os.path.join(root, icon)
                    if os.path.exists(icon_path):
                        icon_name = icon
                        break

                try:
                    ini_content = ""
                    ini_path = os.path.join(root, "desktop.ini")

                    if icon_name:
                        # إذا كانت الأيقونة غير افتراضية، استخدم اسم الأيقونة فقط
                        ini_content = f"""[.ShellClassInfo]
IconResource={icon_name},0"""
                    elif self.use_default_icon and not os.path.exists(ini_path):
                        # إذا لم تكن هناك أيقونة، واستخدام الأيقونة الافتراضية مفعّل
                        ini_content = f"""[.ShellClassInfo]
IconResource={os.path.abspath(self.default_icon)},0"""

                    if ini_content:
                        if os.path.exists(ini_path):
                            os.remove(ini_path)

                        with open(ini_path, "w") as ini_file:
                            ini_file.write(ini_content)

                        os.system(f'attrib +h "{ini_path}"')  # جعل ملف desktop.ini مخفيًا
                        os.system(f'attrib +s "{root}"')  # جعل المجلد نظاميًا
                        os.system(f'attrib +r "{root}"')  # جعل المجلد للقراءة فقط

                        if icon_name:
                            print(f"تم تعيين الأيقونة '{icon_name}' لمجلد: {root}")
                        elif self.use_default_icon:
                            print(f"تم تعيين الأيقونة الافتراضية لمجلد: {root}")

                    self.progress.emit(int((i + 1) / total_folders * 100))  # تحديث شريط التقدم

                except Exception as e:
                    print(f"خطأ أثناء إعداد desktop.ini في المجلد {root}: {e}")

            self.finished.emit("تم إنشاء ملفات desktop.ini بنجاح!")
        except Exception as e:
            self.finished.emit(f"حدث خطأ أثناء العملية: {e}")

class ArchiveThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, input_folder, archive_folder):
        super().__init__()
        self.input_folder = input_folder
        self.archive_folder = archive_folder

    def run(self):
        try:
            # إنشاء مجلد الأرشيف إذا لم يكن موجودًا
            os.makedirs(self.archive_folder, exist_ok=True)

            # استعراض المجلدات والملفات
            folders = []
            for root, _, _ in os.walk(self.input_folder):
                folders.append(root)

            total_folders = len(folders)
            for i, root in enumerate(folders):
                # إنشاء المجلد المقابل داخل مجلد الأرشيف
                relative_path = os.path.relpath(root, self.input_folder)
                archive_subfolder = os.path.join(self.archive_folder, relative_path)
                os.makedirs(archive_subfolder, exist_ok=True)

                # نسخ الأيقونات وملف desktop.ini إلى المجلد الجديد
                for filename in os.listdir(root):
                    if filename.lower().endswith(("ico", "png", "jpg", "jpeg")) or filename.lower() == "desktop.ini":
                        source_path = os.path.join(root, filename)
                        destination_path = os.path.join(archive_subfolder, filename)
                        try:
                            shutil.copy2(source_path, destination_path)
                            print(f"تم أرشفة الملف: {destination_path}")

                            # إذا كان الملف هو desktop.ini، نحافظ على خصائصه
                            if filename.lower() == "desktop.ini":
                                os.system(f'attrib +h "{destination_path}"')  # جعل الملف مخفيًا
                                os.system(f'attrib +s "{archive_subfolder}"')  # جعل المجلد نظاميًا
                                os.system(f'attrib +r "{archive_subfolder}"')  # جعل المجلد للقراءة فقط
                                print(f"تم تعيين خصائص ملف desktop.ini في: {destination_path}")

                        except Exception as e:
                            print(f"خطأ أثناء نسخ {source_path}: {e}")

                # تعيين الأيقونات في الأرشيف بنفس الطريقة
                self.set_icon_for_folder(archive_subfolder)

                self.progress.emit(int((i + 1) / total_folders * 100))  # تحديث شريط التقدم

            self.finished.emit("تم الانتهاء من أرشفة الأيقونات وملفات desktop.ini مع تعيين الأيقونات!")
        except Exception as e:
            self.finished.emit(f"حدث خطأ أثناء العملية: {e}")

    def set_icon_for_folder(self, folder_path):
        """
        تعيين الأيقونة للمجلد في الأرشيف بنفس الطريقة التي تم تعيينها في المجلد الأصلي.
        """
        desktop_ini_path = os.path.join(folder_path, "desktop.ini")
        if os.path.exists(desktop_ini_path):
            try:
                # جعل ملف desktop.ini مخفيًا
                os.system(f'attrib +h "{desktop_ini_path}"')

                # جعل المجلد نظاميًا وقراءة فقط
                os.system(f'attrib +s "{folder_path}"')
                os.system(f'attrib +r "{folder_path}"')

                print(f"تم تعيين الأيقونة للمجلد: {folder_path}")
            except Exception as e:
                print(f"خطأ أثناء تعيين الأيقونة للمجلد {folder_path}: {e}")

class IconDownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)

    def __init__(self, folder_path, possible_icons, subfolder_levels, api_source):
        super().__init__()
        self.folder_path = folder_path
        self.possible_icons = possible_icons
        self.subfolder_levels = subfolder_levels
        self.api_source = api_source  # مصدر البحث (MyAnimeList, TMDB, RAWG, إلخ)

    def run(self):
        try:
            folders = []
            for root, _, _ in os.walk(self.folder_path):
                level = root.replace(self.folder_path, '').count(os.sep)
                if level == self.subfolder_levels:
                    folders.append(root)

            total_folders = len(folders)
            for i, folder in enumerate(folders):
                has_icon = False
                for icon in self.possible_icons:
                    icon_path = os.path.join(folder, icon)
                    if os.path.exists(icon_path):
                        has_icon = True
                        break

                if not has_icon:
                    item_name = os.path.basename(folder)
                    print(f"جارٍ تحميل الغلاف: {item_name}")
                    if self.api_source == "MyAnimeList":
                        self.download_MyAnimeList_cover(item_name, folder)
                    elif self.api_source == "Anilist":
                        self.download_Anilist_cover(item_name, folder)
                    elif self.api_source == "TVmaze":
                        self.download_tvmaze_cover(item_name, folder)
                    elif self.api_source == "OMDb":
                        self.download_omdb_cover(item_name, folder)
                    elif self.api_source == "RAWG":
                        self.download_rawg_cover(item_name, folder)

                self.progress.emit(int((i + 1) / total_folders * 100))

            self.finished.emit("تم تحميل الأيقونات بنجاح!")
        except Exception as e:
            self.finished.emit(f"حدث خطأ أثناء العملية: {e}")

    def download_MyAnimeList_cover(self, anime_name, save_path):
        search_url = f"https://api.jikan.moe/v4/anime?q={anime_name}"
        response = requests.get(search_url)

        if response.status_code == 200:
            data = response.json()
            if data["data"]:
                anime = data["data"][0]
                print(f"العنوان: {anime['title']}")
                print(f"الصورة: {anime['images']['jpg']['large_image_url']}")

                image_url = anime["images"]["jpg"]["large_image_url"]
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    image_name = f"{anime_name}_cover.jpg"
                    full_path = os.path.join(save_path, image_name)

                    with open(full_path, "wb") as file:
                        file.write(image_response.content)
                    print(f"تم حفظ الصورة في: {full_path}")
                else:
                    print("حدث خطأ أثناء تحميل الصورة.")
            else:
                print("لم يتم العثور على أنمي بهذا الاسم.")
        else:
            print("حدث خطأ أثناء الاتصال بالـ API.")

    def download_Anilist_cover(self, anime_name, save_path):
        query = '''
        query ($search: String) {
            Media (search: $search, type: ANIME) {
                title {
                    romaji
                    english
                    native
                }
                coverImage {
                    large
                }
            }
        }
        '''
        variables = {'search': anime_name}
        url = 'https://graphql.anilist.co'
        response = requests.post(url, json={'query': query, 'variables': variables})

        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("Media"):
                anime = data["data"]["Media"]
                print(f"العنوان: {anime['title']['romaji']}")
                print(f"الصورة: {anime['coverImage']['large']}")

                image_url = anime["coverImage"]["large"]
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    image_name = f"{anime_name}_cover.jpg"
                    full_path = os.path.join(save_path, image_name)

                    with open(full_path, "wb") as file:
                        file.write(image_response.content)
                    print(f"تم حفظ الصورة في: {full_path}")
                else:
                    print("حدث خطأ أثناء تحميل الصورة.")
            else:
                print("لم يتم العثور على أنمي بهذا الاسم.")
        else:
            print("حدث خطأ أثناء الاتصال بالـ API.")


    def download_tvmaze_cover(series_name, save_path):
        search_url = f"https://api.tvmaze.com/singlesearch/shows?q={series_name}"
        response = requests.get(search_url)

        if response.status_code == 200:
            data = response.json()
            if data.get("image"):
                print(f"العنوان: {data['name']}")
                print(f"الصورة: {data['image']['original']}")

                image_url = data["image"]["original"]
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    image_name = f"{series_name}_cover.jpg"
                    full_path = os.path.join(save_path, image_name)

                    with open(full_path, "wb") as file:
                        file.write(image_response.content)
                    print(f"تم حفظ الصورة في: {full_path}")
                else:
                    print("حدث خطأ أثناء تحميل الصورة.")
            else:
                print("لم يتم العثور على مسلسل بهذا الاسم.")
        else:
            print("حدث خطأ أثناء الاتصال بالـ API.")

    def download_omdb_cover(movie_name, save_path):
        api_key = "YOUR_OMDB_API_KEY"  # استبدل بمفتاح API الخاص بك
        search_url = f"http://www.omdbapi.com/?apikey={api_key}&t={movie_name}"
        response = requests.get(search_url)

        if response.status_code == 200:
            data = response.json()
            if data.get("Poster"):
                print(f"العنوان: {data['Title']}")
                print(f"الصورة: {data['Poster']}")

                image_url = data["Poster"]
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    image_name = f"{movie_name}_cover.jpg"
                    full_path = os.path.join(save_path, image_name)

                    with open(full_path, "wb") as file:
                        file.write(image_response.content)
                    print(f"تم حفظ الصورة في: {full_path}")
                else:
                    print("حدث خطأ أثناء تحميل الصورة.")
            else:
                print("لم يتم العثور على فيلم بهذا الاسم.")
        else:
            print("حدث خطأ أثناء الاتصال بالـ API.")


    def download_rawg_cover(self, game_name, save_path):
        api_key = "2dd51b0ad64e44678c35d75543ad3e3f"  # مفتاح RAWG API الخاص بك
        search_url = f"https://api.rawg.io/api/games?key={api_key}&search={game_name}"
        response = requests.get(search_url)

        if response.status_code == 200:
            data = response.json()
            if data["results"]:
                game = data["results"][0]
                print(f"العنوان: {game['name']}")
                print(f"الصورة: {game['background_image']}")

                image_url = game["background_image"]
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    image_name = f"{game_name}_cover.jpg"
                    full_path = os.path.join(save_path, image_name)

                    with open(full_path, "wb") as file:
                        file.write(image_response.content)
                    print(f"تم حفظ الصورة في: {full_path}")
                else:
                    print("حدث خطأ أثناء تحميل الصورة.")
            else:
                print("لم يتم العثور على لعبة بهذا الاسم.")
        else:
            print("حدث خطأ أثناء الاتصال بالـ API.")

# واجهة المستخدم باستخدام PyQt5
class IconConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("تحويل الصور إلى أيقونات")
        self.setGeometry(100, 100, 600, 450)  # زيادة الارتفاع لإضافة الأزرار الجديدة

        # إضافة أيقونة للتطبيق
        icon_path = r"E:\vs\py\app_icon.ico"  # المسار المطلق للأيقونة
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            QMessageBox.warning(self, "تحذير", "لم يتم العثور على ملف الأيقونة!")

        # إنشاء تخطيط رئيسي
        main_layout = QVBoxLayout()

        # حقول الإدخال (غير متغيرة)
        self.folder_path_label = QLabel("المجلد الرئيسي:", self)
        self.folder_path_entry = QLineEdit(self)
        self.folder_path_entry.setText(self.settings["main_path"])
        self.browse_folder_button = QPushButton("استعراض", self)
        self.browse_folder_button.clicked.connect(lambda: self.browse_path(self.folder_path_entry))

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_path_label)
        folder_layout.addWidget(self.folder_path_entry)
        folder_layout.addWidget(self.browse_folder_button)
        main_layout.addLayout(folder_layout)

        self.backup_folder_label = QLabel("مجلد النسخ الاحتياطي:", self)
        self.backup_folder_label.setWordWrap(True)  # تفعيل التفاف النص
        self.backup_folder_entry = QLineEdit(self)
        self.backup_folder_entry.setText(self.settings["original_folder"])
        self.browse_backup_button = QPushButton("استعراض", self)
        self.browse_backup_button.clicked.connect(lambda: self.browse_path(self.backup_folder_entry))

        backup_layout = QHBoxLayout()
        backup_layout.addWidget(self.backup_folder_label)
        backup_layout.addWidget(self.backup_folder_entry)
        backup_layout.addWidget(self.browse_backup_button)
        main_layout.addLayout(backup_layout)

        self.archive_folder_label = QLabel("مجلد الأرشيف:", self)
        self.archive_folder_entry = QLineEdit(self)
        self.archive_folder_entry.setText(self.settings.get("archive_folder", ""))
        self.browse_archive_button = QPushButton("استعراض", self)
        self.browse_archive_button.clicked.connect(lambda: self.browse_path(self.archive_folder_entry))

        archive_layout = QHBoxLayout()
        archive_layout.addWidget(self.archive_folder_label)
        archive_layout.addWidget(self.archive_folder_entry)
        archive_layout.addWidget(self.browse_archive_button)
        main_layout.addLayout(archive_layout)

        self.format_label = QLabel("الصيغ المدعومة (مفصولة بفاصلة):", self)
        self.format_entry = QLineEdit(self)
        self.format_entry.setText(self.settings["supported_formats"])
        main_layout.addWidget(self.format_label)
        main_layout.addWidget(self.format_entry)

        self.icon_label = QLabel("أسماء الأيقونات المحتملة (مفصولة بفاصلة):", self)
        self.icon_entry = QLineEdit(self)
        self.icon_entry.setText(self.settings["possible_icons"])
        main_layout.addWidget(self.icon_label)
        main_layout.addWidget(self.icon_entry)

        self.default_icon_label = QLabel("الأيقونة الافتراضية:", self)
        self.default_icon_entry = QLineEdit(self)
        self.default_icon_entry.setText(self.settings["default_icon"])
        self.browse_icon_button = QPushButton("استعراض", self)
        self.browse_icon_button.clicked.connect(lambda: self.browse_path(self.default_icon_entry, is_file=True))

        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.default_icon_label)
        icon_layout.addWidget(self.default_icon_entry)
        icon_layout.addWidget(self.browse_icon_button)
        main_layout.addLayout(icon_layout)

        self.use_default_icon_check = QCheckBox("استخدام الأيقونة الافتراضية", self)
        self.use_default_icon_check.setChecked(self.settings["use_default_icon"])
        main_layout.addWidget(self.use_default_icon_check)

        # إضافة حقل لتحديد عدد التفرعات
        self.subfolder_levels_label = QLabel("عدد التفرعات:", self)
        self.subfolder_levels_entry = QSpinBox(self)
        self.subfolder_levels_entry.setValue(self.settings.get("subfolder_levels", 2))
        self.subfolder_levels_entry.setRange(1, 10)  # تحديد نطاق عدد التفرعات

        subfolder_layout = QHBoxLayout()
        subfolder_layout.addWidget(self.subfolder_levels_label)
        subfolder_layout.addWidget(self.subfolder_levels_entry)
        main_layout.addLayout(subfolder_layout)

        # شريط التقدم
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # أزرار التنفيذ
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("ابدأ التحويل", self)
        self.start_button.clicked.connect(self.start_conversion)
        button_layout.addWidget(self.start_button)

        self.create_ini_button = QPushButton("إعداد ملفات desktop.ini", self)
        self.create_ini_button.clicked.connect(self.create_ini_files)
        button_layout.addWidget(self.create_ini_button)

        self.archive_button = QPushButton("أرشفة الأيقونات", self)
        self.archive_button.clicked.connect(self.start_archive)
        button_layout.addWidget(self.archive_button)

        self.download_icons_button = QPushButton("تحميل الأيقونات المفقودة", self)
        self.download_icons_button.clicked.connect(self.start_download_icons)
        button_layout.addWidget(self.download_icons_button)

        main_layout.addLayout(button_layout)

        # أزرار إخفاء وإظهار الملفات والأيقونات
        hide_unhide_layout = QHBoxLayout()
        self.hide_files_button = QPushButton("إخفاء الملفات والأيقونات بشكل كامل", self)
        self.hide_files_button.clicked.connect(self.hide_files_and_icons)
        hide_unhide_layout.addWidget(self.hide_files_button)

        self.unhide_files_button = QPushButton("إظهار الملفات والأيقونات", self)
        self.unhide_files_button.clicked.connect(self.unhide_files_and_icons)
        hide_unhide_layout.addWidget(self.unhide_files_button)

        main_layout.addLayout(hide_unhide_layout)

        # إضافة حقل مصدر البحث
        self.api_label = QLabel("مصدر البحث:", self)
        self.api_combo = QComboBox(self)
        self.api_combo.addItem("MyAnimeList")
        self.api_combo.addItem("Anilist")
        self.api_combo.addItem("TVmaze")
        self.api_combo.addItem("OMDb")
        self.api_combo.addItem("RAWG")
        self.api_combo.setCurrentIndex(0)  # افتراضيًا MyAnimeList

        api_layout = QHBoxLayout()
        api_layout.addWidget(self.api_label)
        api_layout.addWidget(self.api_combo)
        main_layout.addLayout(api_layout)  # إضافة api_layout إلى main_layout

        # تعيين التخطيط الرئيسي للنافذة
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # توصيل إشارات textChanged لحفظ الإعدادات تلقائيًا
        self.folder_path_entry.textChanged.connect(self.update_settings)
        self.backup_folder_entry.textChanged.connect(self.update_settings)
        self.archive_folder_entry.textChanged.connect(self.update_settings)
        self.format_entry.textChanged.connect(self.update_settings)
        self.icon_entry.textChanged.connect(self.update_settings)
        self.default_icon_entry.textChanged.connect(self.update_settings)
        self.use_default_icon_check.stateChanged.connect(self.update_settings)
        self.subfolder_levels_entry.valueChanged.connect(self.update_settings)

    def hide_files_and_icons(self):
        """إخفاء desktop.ini والأيقونة بشكل كامل."""
        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        self.hide_unhide_thread = HideUnhideThread(self.settings["main_path"], "hide")
        self.hide_unhide_thread.progress.connect(self.update_progress)
        self.hide_unhide_thread.finished.connect(self.show_message)
        self.hide_unhide_thread.start()

    def unhide_files_and_icons(self):
        """إظهار desktop.ini والأيقونة."""
        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        self.hide_unhide_thread = HideUnhideThread(self.settings["main_path"], "unhide")
        self.hide_unhide_thread.progress.connect(self.update_progress)
        self.hide_unhide_thread.finished.connect(self.show_message)
        self.hide_unhide_thread.start()

    def browse_path(self, entry, is_file=False):
        """
        فتح نافذة استعراض الملفات أو المجلدات مع البدء من المسار المحدد في حقل الإدخال.
        """
        # الحصول على المسار الحالي من حقل الإدخال
        current_path = entry.text()

        # إذا لم يكن هناك مسار محدد، نستخدم المسار الافتراضي (مجلد الكود)
        if not current_path or not os.path.exists(current_path):
            current_path = os.getcwd()  # مجلد الكود الحالي

        if is_file:
            # استعراض الملفات (لاختيار الأيقونة الافتراضية)
            path, _ = QFileDialog.getOpenFileName(self, "اختر ملف الأيقونة", current_path, "ICO Files (*.ico)")
        else:
            # استعراض المجلدات
            path = QFileDialog.getExistingDirectory(self, "اختر مجلد", current_path)

        # تعيين المسار المحدد في حقل الإدخال
        if path:
            entry.setText(path)

    def update_settings(self):
        """
        تحديث الإعدادات وحفظها عند تغيير النص في الحقول.
        """
        self.settings["main_path"] = self.folder_path_entry.text()
        self.settings["original_folder"] = self.backup_folder_entry.text()
        self.settings["archive_folder"] = self.archive_folder_entry.text()
        self.settings["supported_formats"] = self.format_entry.text()
        self.settings["possible_icons"] = self.icon_entry.text()
        self.settings["default_icon"] = self.default_icon_entry.text()
        self.settings["use_default_icon"] = int(self.use_default_icon_check.isChecked())
        self.settings["subfolder_levels"] = self.subfolder_levels_entry.value()
        save_settings(self.settings)

    def start_conversion(self):
        supported_formats = tuple(self.settings["supported_formats"].split(","))
        self.progress_bar.setValue(0)  # إعادة تعيين شريط التقدم

        self.conversion_thread = ConversionThread(self.settings["main_path"], self.settings["original_folder"], supported_formats)
        self.conversion_thread.progress.connect(self.update_progress)
        self.conversion_thread.finished.connect(self.show_message)
        self.conversion_thread.start()

    def create_ini_files(self):
        possible_icons = self.settings["possible_icons"].split(",")

        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        if self.settings["use_default_icon"] and not os.path.exists(self.settings["default_icon"]):
            QMessageBox.critical(self, "خطأ", "الأيقونة الافتراضية غير موجودة.")
            return

        self.progress_bar.setValue(0)  # إعادة تعيين شريط التقدم

        self.ini_thread = DesktopIniThread(self.settings["main_path"], possible_icons, self.settings["default_icon"], self.settings["use_default_icon"])
        self.ini_thread.progress.connect(self.update_progress)
        self.ini_thread.finished.connect(self.show_message)
        self.ini_thread.start()

    def set_default_icons(self):
        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        if not os.path.exists(self.settings["default_icon"]):
            QMessageBox.critical(self, "خطأ", "الأيقونة الافتراضية غير موجودة.")
            return

        self.progress_bar.setValue(0)  # إعادة تعيين شريط التقدم

        self.ini_thread = DesktopIniThread(self.settings["main_path"], [], self.settings["default_icon"], self.settings["use_default_icon"])
        self.ini_thread.progress.connect(self.update_progress)
        self.ini_thread.finished.connect(self.show_message)
        self.ini_thread.start()

    def start_archive(self):
        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        if not os.path.exists(self.settings["archive_folder"]):
            QMessageBox.critical(self, "خطأ", "مجلد الأرشيف غير موجود.")
            return

        self.progress_bar.setValue(0)  # إعادة تعيين شريط التقدم

        self.archive_thread = ArchiveThread(self.settings["main_path"], self.settings["archive_folder"])
        self.archive_thread.progress.connect(self.update_progress)
        self.archive_thread.finished.connect(self.show_message)
        self.archive_thread.start()

    def start_download_icons(self):
        if not os.path.exists(self.settings["main_path"]):
            QMessageBox.critical(self, "خطأ", "المسار الرئيسي غير موجود.")
            return

        possible_icons = self.settings["possible_icons"].split(",")
        subfolder_levels = self.settings["subfolder_levels"]
        api_source = self.api_combo.currentText()  # الحصول على مصدر البحث المحدد

        self.progress_bar.setValue(0)  # إعادة تعيين شريط التقدم

        self.download_icons_thread = IconDownloadThread(self.settings["main_path"], possible_icons, subfolder_levels, api_source)
        self.download_icons_thread.progress.connect(self.update_progress)
        self.download_icons_thread.finished.connect(self.show_message)
        self.download_icons_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)  # تحديث شريط التقدم

    def show_message(self, message):
        QMessageBox.information(self, "تم", message)

if __name__ == "__main__":
    app = QApplication([])
    
    # تعيين أيقونة للتطبيق
    icon_path = r"E:\vs\py\app_icon.ico"  # المسار المطلق للأيقونة
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        QMessageBox.warning(None, "تحذير", "لم يتم العثور على ملف الأيقونة!")

    window = IconConverterApp()
    window.show()
    app.exec_()