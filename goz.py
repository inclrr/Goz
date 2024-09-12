import sys
import os
import time
import json
import random
import csv
from datetime import datetime, date, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QProgressBar, QSystemTrayIcon, QMenu, QAction, QMessageBox, QDialog, QLineEdit, 
                             QCheckBox, QComboBox, QDesktopWidget, QCalendarWidget, QTableWidget, 
                             QTableWidgetItem, QTabWidget, QSlider, QSpinBox, QTimeEdit, QFileDialog, QScrollArea,
                             QShortcut, QGraphicsOpacityEffect)
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap, QImage, QKeySequence
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDate, QSettings, QTime, QUrl, QTranslator, QLocale, QPropertyAnimation, QEasingCurve, QEvent, QThread
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from plyer import notification
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class ComputerUsageTracker(QThread):
    update_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.usage_time = 0
        self.is_running = True

    def run(self):
        while self.is_running:
            self.usage_time += 1
            self.update_signal.emit(self.usage_time)
            time.sleep(60)  # Her dakika güncelle

    def stop(self):
        self.is_running = False

class GozDinlendirmeUygulamasi(QMainWindow):
    update_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Göz Dinlendirme Asistanı")
        self.setGeometry(100, 100, 400, 700)
        self.setWindowIcon(QIcon("goz_icon.png"))

        self.settings = QSettings("GozDinlendirmeAsistani", "Ayarlar")
        self.load_settings()
        self.init_ui()
        self.create_tray_icon()

        self.calisma_durumu = True
        self.kalan_sure = self.calisma_suresi
        self.gunluk_dinlenme_sayisi = self.settings.value("gunluk_dinlenme_sayisi", 0, type=int)
        self.son_dinlenme_tarihi = self.settings.value("son_dinlenme_tarihi", QDate.currentDate())
        self.haftalik_istatistikler = self.settings.value("haftalik_istatistikler", {}, type=dict)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

        self.update_signal.connect(self.update_ui)
        self.apply_theme()
        self.center_on_screen()

        self.check_daily_reset()
        self.load_weekly_statistics()

        self.player = QMediaPlayer()
        
        self.translator = QTranslator()
        self.load_language()

        self.auto_start_timer = QTimer(self)
        self.auto_start_timer.timeout.connect(self.check_auto_start)
        self.auto_start_timer.start(60000)  # Her dakika kontrol et

        self.daily_goal = self.settings.value("daily_goal", 8, type=int)
        self.smart_mode = self.settings.value("smart_mode", False, type=bool)

        self.current_version = "1.1.0"
        self.check_updates()

        self.create_shortcuts()

        # Bilgisayar kullanım süresi takibi
        self.usage_tracker = ComputerUsageTracker()
        self.usage_tracker.update_signal.connect(self.update_usage_time)
        self.usage_tracker.start()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Logo ve başlık
        header_layout = QHBoxLayout()
        self.logo_label = QLabel(self)
        pixmap = QPixmap("goz_icon.png").scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pixmap)
        header_layout.addWidget(self.logo_label)
        
        title_label = QLabel("Göz Dinlendirme Asistanı", self)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Durum ve kalan süre
        self.durum_label = QLabel("Durum: Çalışıyor", self)
        self.durum_label.setAlignment(Qt.AlignCenter)
        self.durum_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.durum_label)

        self.kalan_sure_label = QLabel(f"Kalan Süre: {self.calisma_suresi // 60:02d}:00", self)
        self.kalan_sure_label.setAlignment(Qt.AlignCenter)
        self.kalan_sure_label.setFont(QFont("Arial", 24, QFont.Bold))
        layout.addWidget(self.kalan_sure_label)

        # İlerleme çubuğu
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Butonlar
        button_layout = QHBoxLayout()
        self.ayarlar_button = self.create_styled_button("Ayarlar", self.ayarlar_penceresi_ac)
        button_layout.addWidget(self.ayarlar_button)

        self.egzersiz_button = self.create_styled_button("Göz Egzersizi", self.show_exercise_video)
        button_layout.addWidget(self.egzersiz_button)

        self.istatistikler_button = self.create_styled_button("İstatistikler", self.show_detailed_statistics)
        button_layout.addWidget(self.istatistikler_button)

        layout.addLayout(button_layout)

        # İpuçları ve motivasyon mesajları
        self.ipucu_label = QLabel("", self)
        self.ipucu_label.setAlignment(Qt.AlignCenter)
        self.ipucu_label.setWordWrap(True)
        self.ipucu_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.ipucu_label)

        self.goz_sagligi_ipucu_goster()

        self.motivation_label = QLabel("", self)
        self.motivation_label.setAlignment(Qt.AlignCenter)
        self.motivation_label.setWordWrap(True)
        self.motivation_label.setStyleSheet("font-style: italic; color: #555;")
        layout.addWidget(self.motivation_label)
        self.update_motivation_message()

        # Pomodoro modu butonu
        self.pomodoro_button = self.create_styled_button("Pomodoro Modu", self.toggle_pomodoro_mode)
        layout.addWidget(self.pomodoro_button)

        # Ses seviyesi kontrolü
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Ses Seviyesi:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)

        # Çalışma süresi ayarı
        work_time_layout = QHBoxLayout()
        work_time_layout.addWidget(QLabel("Çalışma Süresi (dakika):"))
        self.work_time_slider = QSlider(Qt.Horizontal)
        self.work_time_slider.setRange(10, 60)
        self.work_time_slider.setValue(self.calisma_suresi // 60)
        self.work_time_slider.valueChanged.connect(self.update_work_time)
        work_time_layout.addWidget(self.work_time_slider)
        layout.addLayout(work_time_layout)

        # Günlük hedef ayarı
        goal_layout = QHBoxLayout()
        goal_layout.addWidget(QLabel("Günlük Hedef (dinlenme sayısı):"))
        self.daily_goal_spinbox = QSpinBox()
        self.daily_goal_spinbox.setRange(1, 20)
        self.daily_goal_spinbox.setValue(self.daily_goal)
        self.daily_goal_spinbox.valueChanged.connect(self.update_daily_goal)
        goal_layout.addWidget(self.daily_goal_spinbox)
        layout.addLayout(goal_layout)

        # Akıllı mod
        self.smart_mode_checkbox = QCheckBox("Akıllı Mod")
        self.smart_mode_checkbox.setChecked(self.smart_mode)
        self.smart_mode_checkbox.stateChanged.connect(self.toggle_smart_mode)
        layout.addWidget(self.smart_mode_checkbox)

        # Göz yorgunluğu tahmini
        self.fatigue_label = QLabel("Göz Yorgunluğu Tahmini: ")
        layout.addWidget(self.fatigue_label)

        # Bilgisayar kullanım süresi
        self.usage_time_label = QLabel("Bilgisayar Kullanım Süresi: 0 dakika")
        layout.addWidget(self.usage_time_label)

    def create_styled_button(self, text, connection):
        button = QPushButton(text, self)
        button.clicked.connect(connection)
        button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
        """)
        return button

    def set_volume(self, value):
        self.player.setVolume(value)

    def update_work_time(self, value):
        self.calisma_suresi = value * 60
        self.kalan_sure = self.calisma_suresi
        self.save_settings()
        self.update_signal.emit()

    def update_motivation_message(self):
        messages = [
            self.tr("Gözlerinizi dinlendirmek, verimliliğinizi artırır!"),
            self.tr("Düzenli molalar, göz sağlığınız için çok önemlidir."),
            self.tr("Gözlerinizi koruyun, geleceğinizi aydınlatın!"),
            self.tr("Kısa bir mola, uzun vadeli sağlık demektir."),
            self.tr("Gözleriniz sizin pencereniz, onlara iyi bakın!")
        ]
        self.motivation_label.setText(random.choice(messages))

    def update_usage_time(self, time):
        hours, minutes = divmod(time, 60)
        self.usage_time_label.setText(f"Bilgisayar Kullanım Süresi: {hours} saat {minutes} dakika")
        if time % 60 == 0 and time > 0:  # Her saat başı uyarı
            self.show_usage_warning(hours)

    def show_usage_warning(self, hours):
        warning_message = f"{hours} saattir bilgisayar kullanıyorsunuz. Lütfen biraz ara verin ve gözlerinizi dinlendirin."
        QMessageBox.warning(self, "Uzun Süreli Kullanım Uyarısı", warning_message)

    def goz_dinlendirme_hatirlatici(self):
        self.calisma_durumu = False
        message = f"Lütfen {self.dinlenme_suresi} saniye boyunca 6 metre uzağa bakın!"
        if self.dil == "en":
            message = f"Please look 6 meters away for {self.dinlenme_suresi} seconds!"

        notification.notify(
            title=self.tr("Göz Dinlendirme Zamanı"),
            message=self.tr(message),
            app_icon="goz_icon.png",
            timeout=10
        )

        if self.sesli_uyari:
            self.play_sound(self.settings.value("sound_file", "notification.mp3"))

        self.durum_label.setText(self.tr("Durum: Dinleniyor"))
        QTimer.singleShot(self.dinlenme_suresi * 1000, self.dinlenme_bitti)

        # Animasyon efekti
        self.animate_label(self.durum_label)

    def animate_label(self, label):
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(1000)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()

    def play_sound(self, sound_file):
        full_path = os.path.join(os.path.dirname(__file__), sound_file)
        url = QUrl.fromLocalFile(full_path)
        content = QMediaContent(url)
        self.player.setMedia(content)
        self.player.play()

    def dinlenme_bitti(self):
        self.calisma_durumu = True
        self.kalan_sure = self.calisma_suresi
        self.gunluk_dinlenme_sayisi += 1
        self.goz_sagligi_ipucu_goster()
        self.durum_label.setText(self.tr("Durum: Çalışıyor"))
        self.update_signal.emit()

        current_date = QDate.currentDate()
        if current_date != self.son_dinlenme_tarihi:
            self.gunluk_dinlenme_sayisi = 1
            self.son_dinlenme_tarihi = current_date

        self.update_weekly_statistics()
        self.save_settings()
        self.check_daily_goal()

        # Animasyon efekti
        self.animate_label(self.durum_label)

    def check_daily_goal(self):
        if self.gunluk_dinlenme_sayisi >= self.daily_goal:
            QMessageBox.information(self, self.tr("Tebrikler!"), 
                                    self.tr("Günlük hedefinize ulaştınız! Gözleriniz için harika bir iş çıkardınız."))

    def update_daily_goal(self, value):
        self.daily_goal = value
        self.save_settings()

    def toggle_smart_mode(self, state):
        self.smart_mode = state == Qt.Checked
        self.save_settings()
        if self.smart_mode:
            self.adjust_timings_smart_mode()

    def adjust_timings_smart_mode(self):
        current_hour = QTime.currentTime().hour()
        if 9 <= current_hour < 12 or 14 <= current_hour < 17:
            self.calisma_suresi = 25 * 60  # Yoğun çalışma saatleri
        elif 12 <= current_hour < 14:
            self.calisma_suresi = 20 * 60  # Öğle arası civarı
        else:
            self.calisma_suresi = 30 * 60  # Diğer saatler

        self.kalan_sure = self.calisma_suresi
        self.update_signal.emit()

    def ayarlar_penceresi_ac(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Ayarlar"))
        layout = QVBoxLayout(dialog)

        calisma_suresi_input = QLineEdit(str(self.calisma_suresi // 60))
        layout.addWidget(QLabel(self.tr("Çalışma Süresi (dakika):")))
        layout.addWidget(calisma_suresi_input)

        dinlenme_suresi_input = QLineEdit(str(self.dinlenme_suresi))
        layout.addWidget(QLabel(self.tr("Dinlenme Süresi (saniye):")))
        layout.addWidget(dinlenme_suresi_input)

        baslangicta_calistir_check = QCheckBox(self.tr("Bilgisayar açıldığında çalıştır"))
        baslangicta_calistir_check.setChecked(self.baslangicta_calistir)
        layout.addWidget(baslangicta_calistir_check)

        sesli_uyari_check = QCheckBox(self.tr("Sesli uyarı"))
        sesli_uyari_check.setChecked(self.sesli_uyari)
        layout.addWidget(sesli_uyari_check)

        dil_combo = QComboBox()
        dil_combo.addItems(["Türkçe", "English"])
        dil_combo.setCurrentIndex(0 if self.dil == "tr" else 1)
        layout.addWidget(QLabel(self.tr("Dil:")))
        layout.addWidget(dil_combo)

        tema_combo = QComboBox()
        tema_combo.addItems([self.tr("Açık"), self.tr("Koyu"), self.tr("Mavi"), self.tr("Yeşil")])
        tema_combo.setCurrentIndex(["light", "dark", "blue", "green"].index(self.tema))
        layout.addWidget(QLabel(self.tr("Tema:")))
        layout.addWidget(tema_combo)

        self.sound_file_input = QLineEdit(self.settings.value("sound_file", "notification.mp3"))
        layout.addWidget(QLabel(self.tr("Bildirim Ses Dosyası:")))
        layout.addWidget(self.sound_file_input)

        sound_file_button = QPushButton(self.tr("Ses Dosyası Seç"))
        sound_file_button.clicked.connect(self.select_sound_file)
        layout.addWidget(sound_file_button)

        self.auto_start_time = QTimeEdit()
        self.auto_start_time.setTime(QTime.fromString(self.settings.value("auto_start_time", "09:00")))
        layout.addWidget(QLabel(self.tr("Otomatik Başlatma Zamanı:")))
        layout.addWidget(self.auto_start_time)

        kaydet_button = QPushButton(self.tr("Kaydet"))
        kaydet_button.clicked.connect(lambda: self.ayarlari_kaydet(
            int(calisma_suresi_input.text()) * 60,
            int(dinlenme_suresi_input.text()),
            baslangicta_calistir_check.isChecked(),
            sesli_uyari_check.isChecked(),
            "tr" if dil_combo.currentText() == "Türkçe" else "en",
            ["light", "dark", "blue", "green"][tema_combo.currentIndex()],
            dialog
        ))
        layout.addWidget(kaydet_button)

        dialog.exec_()

    def select_sound_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, self.tr("Ses Dosyası Seç"), "", "Ses Dosyaları (*.mp3 *.wav)")
        if file_name:
            self.sound_file_input.setText(file_name)

    def ayarlari_kaydet(self, calisma_suresi, dinlenme_suresi, baslangicta_calistir, sesli_uyari, dil, tema, dialog):
        self.calisma_suresi = calisma_suresi
        self.dinlenme_suresi = dinlenme_suresi
        self.baslangicta_calistir = baslangicta_calistir
        self.sesli_uyari = sesli_uyari
        self.dil = dil
        self.tema = tema

        if self.baslangicta_calistir:
            add_to_startup()
        else:
            remove_from_startup()

        self.kalan_sure = self.calisma_suresi
        self.settings.setValue("sound_file", self.sound_file_input.text())
        self.settings.setValue("auto_start_time", self.auto_start_time.time().toString())
        self.save_settings()
        self.apply_theme()
        self.load_language()
        self.update_signal.emit()
        dialog.accept()
        QMessageBox.information(self, self.tr("Bilgi"), self.tr("Ayarlar başarıyla kaydedildi."))

    def apply_theme(self):
        if self.tema == "light":
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #f0f0f0; color: #333333; }
                QPushButton { background-color: #4CAF50; color: white; border: none; padding: 5px 10px; }
                QPushButton:hover { background-color: #45a049; }
                QLabel { color: #333333; }
            """)
        elif self.tema == "dark":
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #333333; color: #f0f0f0; }
                QPushButton { background-color: #4CAF50; color: white; border: none; padding: 5px 10px; }
                QPushButton:hover { background-color: #45a049; }
                QLabel { color: #f0f0f0; }
            """)
        elif self.tema == "blue":
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #E3F2FD; color: #1565C0; }
                QPushButton { background-color: #1E88E5; color: white; border: none; padding: 5px 10px; }
                QPushButton:hover { background-color: #1976D2; }
                QLabel { color: #1565C0; }
            """)
        elif self.tema == "green":
            self.setStyleSheet("""
                QMainWindow, QDialog { background-color: #E8F5E9; color: #2E7D32; }
                QPushButton { background-color: #43A047; color: white; border: none; padding: 5px 10px; }
                QPushButton:hover { background-color: #388E3C; }
                QLabel { color: #2E7D32; }
            """)

    def show_exercise_video(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Göz Egzersizi Rehberi"))
        layout = QVBoxLayout(dialog)

        video_widget = QVideoWidget()
        layout.addWidget(video_widget)

        player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        player.setVideoOutput(video_widget)

        player.setMedia(QMediaContent(QUrl.fromLocalFile("eye_exercise.mp4")))
        player.play()

        dialog.exec_()

    def show_detailed_statistics(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Detaylı İstatistikler"))
        layout = QVBoxLayout(dialog)

        figure = plt.figure(figsize=(10, 6))
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)

        ax1 = figure.add_subplot(211)
        ax2 = figure.add_subplot(212)

        # Günlük dinlenme sayısı grafiği
        dates = list(self.haftalik_istatistikler.keys())
        counts = list(self.haftalik_istatistikler.values())
        ax1.bar(dates, counts)
        ax1.set_title(self.tr("Günlük Dinlenme Sayısı"))
        ax1.set_xlabel(self.tr("Tarih"))
        ax1.set_ylabel(self.tr("Dinlenme Sayısı"))

        # Ortalama çalışma süresi grafiği
        dates = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        avg_work_times = [45, 50, 40, 55, 48, 30, 25]  # Örnek veri
        ax2.plot(dates, avg_work_times, marker='o')
        ax2.set_title(self.tr("Ortalama Çalışma Süresi"))
        ax2.set_xlabel(self.tr("Gün"))
        ax2.set_ylabel(self.tr("Dakika"))

        plt.tight_layout()
        canvas.draw()

        dialog.exec_()

    def create_shortcuts(self):
        self.shortcut_start = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_start.activated.connect(self.start_timer)

        self.shortcut_pause = QShortcut(QKeySequence("Ctrl+P"), self)
        self.shortcut_pause.activated.connect(self.pause_timer)

        self.shortcut_reset = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_reset.activated.connect(self.reset_timer)

    def start_timer(self):
        if not self.calisma_durumu:
            self.calisma_durumu = True
            self.timer.start(1000)
            self.durum_label.setText(self.tr("Durum: Çalışıyor"))
            self.animate_label(self.durum_label)

    def pause_timer(self):
        if self.calisma_durumu:
            self.calisma_durumu = False
            self.timer.stop()
            self.durum_label.setText(self.tr("Durum: Duraklatıldı"))
            self.animate_label(self.durum_label)

    def reset_timer(self):
        self.kalan_sure = self.calisma_suresi
        self.update_signal.emit()
        if not self.calisma_durumu:
            self.start_timer()

    def estimate_eye_fatigue(self):
        work_time = self.calisma_suresi - self.kalan_sure
        breaks_taken = self.gunluk_dinlenme_sayisi
        fatigue_score = (work_time / 60) - (breaks_taken * 5)
        
        if fatigue_score < 0:
            return self.tr("Düşük")
        elif fatigue_score < 30:
            return self.tr("Orta")
        else:
            return self.tr("Yüksek")

    def update_fatigue_estimate(self):
        fatigue_level = self.estimate_eye_fatigue()
        self.fatigue_label.setText(f"{self.tr('Göz Yorgunluğu Tahmini')}: {fatigue_level}")

    def check_updates(self):
        # Bu fonksiyon, gerçek bir güncelleme kontrolü yapacak şekilde geliştirilmelidir
        new_version = "1.1.1"  # Örnek olarak
        if new_version != self.current_version:
            reply = QMessageBox.question(self, self.tr("Güncelleme Mevcut"),
                                         self.tr(f"Yeni sürüm ({new_version}) mevcut. Güncellemek ister misiniz?"),
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl("https://github.com/your_username/your_repo/releases/latest"))

    def goz_sagligi_ipucu_goster(self):
        ipuclari = [
            self.tr("Ekran parlaklığını ortam ışığına göre ayarlayın."),
            self.tr("Her 20 dakikada bir 20 saniye mola verin."),
            self.tr("Ekranınızı göz hizasının biraz altında tutun."),
            self.tr("Gözlerinizi sık sık nemlendirin, gerekirse suni gözyaşı kullanın."),
            self.tr("Düzenli göz muayenesi yaptırın."),
            self.tr("Yeterli uyku alın, gözlerinizin dinlenmesi için önemlidir."),
            self.tr("Dengeli beslenin, A vitamini ve omega-3 açısından zengin gıdalar tüketin."),
            self.tr("Sigara içmekten kaçının, göz sağlığınızı olumsuz etkiler."),
            self.tr("Güneş gözlüğü kullanarak gözlerinizi UV ışınlarından koruyun."),
            self.tr("Ekran filtreleri kullanarak mavi ışığa maruz kalmanızı azaltın.")
        ]
        self.ipucu_label.setText(random.choice(ipuclari))
        self.animate_label(self.ipucu_label)

    def center_on_screen(self):
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center = QDesktopWidget().screenGeometry(screen).center()
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def check_daily_reset(self):
        current_date = QDate.currentDate()
        if current_date != self.son_dinlenme_tarihi:
            self.gunluk_dinlenme_sayisi = 0
            self.son_dinlenme_tarihi = current_date
            self.save_settings()

    def load_weekly_statistics(self):
        today = date.today()
        for i in range(7):
            day = today - timedelta(days=i)
            if day.strftime("%Y-%m-%d") not in self.haftalik_istatistikler:
                self.haftalik_istatistikler[day.strftime("%Y-%m-%d")] = 0

    def update_weekly_statistics(self):
        today = date.today().strftime("%Y-%m-%d")
        if today in self.haftalik_istatistikler:
            self.haftalik_istatistikler[today] += 1
        else:
            self.haftalik_istatistikler[today] = 1

        # 7 günden eski istatistikleri sil
        cutoff_date = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        self.haftalik_istatistikler = {k: v for k, v in self.haftalik_istatistikler.items() if k >= cutoff_date}

    def toggle_pomodoro_mode(self):
        self.pomodoro_mode = not self.pomodoro_mode
        if self.pomodoro_mode:
            self.calisma_suresi = 25 * 60  # 25 dakika
            self.dinlenme_suresi = 5 * 60  # 5 dakika
            self.pomodoro_button.setText(self.tr("Normal Mod"))
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Pomodoro Modu aktif. 25 dakika çalışma, 5 dakika dinlenme."))
        else:
            self.load_settings()  # Normal ayarlara geri dön
            self.pomodoro_button.setText(self.tr("Pomodoro Modu"))
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Normal Mod aktif."))
        
        self.kalan_sure = self.calisma_suresi
        self.update_signal.emit()
        self.save_settings()

    def check_auto_start(self):
        current_time = QTime.currentTime()
        auto_start_time = QTime.fromString(self.settings.value("auto_start_time", "09:00"))
        if current_time.hour() == auto_start_time.hour() and current_time.minute() == auto_start_time.minute():
            self.start_application()

    def start_application(self):
        self.show()
        self.calisma_durumu = True
        self.kalan_sure = self.calisma_suresi
        self.update_signal.emit()

    def load_language(self):
        if self.dil == "en":
            self.translator.load("goz_dinlendirme_en.qm")
        else:
            self.translator.load("goz_dinlendirme_tr.qm")
        QApplication.instance().installTranslator(self.translator)
        self.retranslateUi()

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Göz Dinlendirme Asistanı"))
        self.durum_label.setText(self.tr("Durum: Çalışıyor"))
        self.ayarlar_button.setText(self.tr("Ayarlar"))
        self.egzersiz_button.setText(self.tr("Göz Egzersizi"))
        self.istatistikler_button.setText(self.tr("İstatistikler"))
        self.pomodoro_button.setText(self.tr("Pomodoro Modu") if not self.pomodoro_mode else self.tr("Normal Mod"))
        self.update_motivation_message()
        self.goz_sagligi_ipucu_goster()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("goz_icon.png"))
        
        show_action = QAction(self.tr("Göster"), self)
        quit_action = QAction(self.tr("Çıkış"), self)
        hide_action = QAction(self.tr("Gizle"), self)

        show_action.triggered.connect(self.show)
        hide_action.triggered.connect(self.hide)
        quit_action.triggered.connect(self.quit_app)

        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            self.tr("Göz Dinlendirme Asistanı"),
            self.tr("Uygulama arka planda çalışmaya devam ediyor."),
            QSystemTrayIcon.Information,
            2000
        )

    def quit_app(self):
        self.save_settings()
        self.calisma_durumu = False
        self.usage_tracker.stop()
        self.usage_tracker.wait()
        QApplication.quit()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                event.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    self.tr("Göz Dinlendirme Asistanı"),
                    self.tr("Uygulama arka planda çalışmaya devam ediyor."),
                    QSystemTrayIcon.Information,
                    2000
                )    

    def save_settings(self):
        self.settings.setValue("calisma_suresi", self.calisma_suresi)
        self.settings.setValue("dinlenme_suresi", self.dinlenme_suresi)
        self.settings.setValue("baslangicta_calistir", self.baslangicta_calistir)
        self.settings.setValue("sesli_uyari", self.sesli_uyari)
        self.settings.setValue("dil", self.dil)
        self.settings.setValue("tema", self.tema)
        self.settings.setValue("gunluk_dinlenme_sayisi", self.gunluk_dinlenme_sayisi)
        self.settings.setValue("son_dinlenme_tarihi", self.son_dinlenme_tarihi)
        self.settings.setValue("haftalik_istatistikler", self.haftalik_istatistikler)
        self.settings.setValue("daily_goal", self.daily_goal)
        self.settings.setValue("smart_mode", self.smart_mode)
        self.settings.setValue("pomodoro_mode", self.pomodoro_mode)

    def load_settings(self):
        self.calisma_suresi = self.settings.value("calisma_suresi", 20 * 60, type=int)
        self.dinlenme_suresi = self.settings.value("dinlenme_suresi", 20, type=int)
        self.baslangicta_calistir = self.settings.value("baslangicta_calistir", False, type=bool)
        self.sesli_uyari = self.settings.value("sesli_uyari", True, type=bool)
        self.dil = self.settings.value("dil", "tr", type=str)
        self.tema = self.settings.value("tema", "light", type=str)
        self.daily_goal = self.settings.value("daily_goal", 8, type=int)
        self.smart_mode = self.settings.value("smart_mode", False, type=bool)
        self.pomodoro_mode = self.settings.value("pomodoro_mode", False, type=bool)

    def update_timer(self):
        if self.calisma_durumu:
            self.kalan_sure -= 1
            if self.kalan_sure <= 0:
                self.goz_dinlendirme_hatirlatici()
            else:
                self.update_signal.emit()
        self.update_fatigue_estimate()

    def update_ui(self):
        minutes, seconds = divmod(self.kalan_sure, 60)
        self.kalan_sure_label.setText(f"{self.tr('Kalan Süre')}: {minutes:02d}:{seconds:02d}")
        progress = int((1 - self.kalan_sure / self.calisma_suresi) * 100)
        self.progress_bar.setValue(progress)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    uygulama = GozDinlendirmeUygulamasi()
    uygulama.show()
    sys.exit(app.exec_())
