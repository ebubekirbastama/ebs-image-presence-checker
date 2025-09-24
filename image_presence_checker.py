#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Görsel Denetleyici (Var/Yok + Kırık Bağlantı Kontrolü)
- Genel yapı korunur (GUI, tablo, log, filtre).
- Blur yok. Sadece:
  * Sayfada hedef görsel var mı?
  * Varsa bu görsellerin URL'leri gerçekten var mı (200 OK, image/*, >0 bayt)?
- Bayraklar: NoImage, BrokenImage (kırık/eksik), "" (sağlam)

Yazar / Developer: Ebubekir Bastama
Repo: https://github.com/ebubekirbastama/image-presence-checker
"""
import io
import csv
import webbrowser
import time
import queue
import threading
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
from ttkbootstrap import Style
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import Frame, Button, Entry, Label, Checkbutton, Spinbox
from tkinter import ttk

__author__ = "Ebubekir Bastama"
__version__ = "1.1.0"
__license__ = "MIT"

# ------------------ HTTP yardımcıları ------------------
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EBSImagePresenceBot/1.1)"}

def fetch(url, timeout=20, stream=False, method="GET", allow_redirects=True):
    if method == "HEAD":
        return requests.head(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=allow_redirects)
    return requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, stream=stream, allow_redirects=allow_redirects)

def verify_image_url(img_url: str, timeout=15) -> tuple[bool, str]:
    """
    Bir görsel URL'sinin GERÇEKTEN var olup olmadığını kontrol eder.
    1) HEAD: 200 ve Content-Type image/* ve Content-Length > 0 ise OK
    2) Aksi halde küçük GET ile doğrula (iter_content ile birkaç byte)
    Döndürür: (ok, detay_mesajı)
    """
    try:
        r = fetch(img_url, timeout=timeout, method="HEAD")
        status = r.status_code
        ctype = r.headers.get("Content-Type", "")
        clen = r.headers.get("Content-Length")
        if status == 200 and ctype.startswith("image/"):
            try:
                if clen is None or int(clen) > 0:
                    return True, f"HEAD OK {status} {ctype} len={clen}"
            except ValueError:
                # Content-Length sayısal değilse yine de OK say
                return True, f"HEAD OK {status} {ctype} len={clen}"
        # bazı sunucular HEAD desteklemez -> GET
        try:
            r2 = fetch(img_url, timeout=timeout, stream=True, method="GET")
            status2 = r2.status_code
            ctype2 = r2.headers.get("Content-Type", "")
            if status2 == 200 and ctype2.startswith("image/"):
                try:
                    chunk = next(r2.iter_content(chunk_size=1024))
                    if chunk and len(chunk) > 0:
                        return True, f"GET OK {status2} {ctype2}"
                except StopIteration:
                    pass
        except Exception as ge:
            return False, f"GET error: {ge}"
        return False, f"Not image or empty (status={status}, type={ctype})"
    except Exception as e:
        return False, f"HEAD error: {e}"

# ------------------ HTML yardımcıları ------------------
def parse_sitemap(sitemap_url: str) -> list:
    urls = []
    try:
        r = fetch(sitemap_url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        if soup.find("sitemapindex"):
            for sm in soup.find_all("sitemap"):
                loc = sm.find("loc")
                if loc and loc.text.strip():
                    urls.extend(parse_sitemap(loc.text.strip()))
        else:
            for u in soup.find_all("url"):
                loc = u.find("loc")
                if loc and loc.text.strip():
                    urls.append(loc.text.strip())
    except Exception:
        pass
    # benzersiz
    seen = set(); out = []
    for u in urls:
        if u not in seen:
            out.append(u); seen.add(u)
    return out

def find_images_in_html(page_url: str, html: str) -> list:
    """
    Öncelik: .post-image .post-image-inner img
    Yoksa genel img/og:image/link[rel=image_src]
    """
    soup = BeautifulSoup(html, "lxml")
    found = []

    focused = soup.select(".post-image .post-image-inner img")
    if focused:
        for img in focused:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src:
                found.append(urljoin(page_url, src))
        return list(dict.fromkeys(found))

    generic = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        generic.add(urljoin(page_url, src))
    for m in soup.find_all("meta", attrs={"property": "og:image"}):
        c = m.get("content")
        if c:
            generic.add(urljoin(page_url, c))
    for l in soup.find_all("link", attrs={"rel": "image_src"}):
        h = l.get("href")
        if h:
            generic.add(urljoin(page_url, h))
    return list(generic)

# ------------------ GUI ------------------
class App:
    def __init__(self, root):
        self.root = root
        self.style = Style("darkly")
        self.root.title("Görsel Denetleyici (Var/Yok + Kırık Kontrol)")
        self.root.geometry("1280x860")
        self.stop_event = threading.Event()
        self.queue = queue.Queue()

        # Veri depoları
        self.all_rows = []   # tüm satırlar
        self.rows = []       # tabloda gösterilen (filtreli) satırlar

        self.log_lines = []

        self._build_top()
        self._build_center()
        self._build_status()

        self.root.after(100, self._drain_queue)

    def _build_top(self):
        p = Frame(self.root, padding=15)
        p.pack(fill=X, side=TOP)

        Label(p, text="Sitemap URL", bootstyle=INFO).grid(row=0, column=0, sticky=W, padx=(0,8))
        self.e_sitemap = Entry(p, width=60)
        # Varsayılan URL güncellendi
        self.e_sitemap.insert(0, "https://ebubekirbastama.com.tr/sitemap.xml")
        self.e_sitemap.grid(row=0, column=1, sticky=EW, padx=(0,12))
        p.columnconfigure(1, weight=1)

        Label(p, text="İş Parçacığı", bootstyle=INFO).grid(row=0, column=2, sticky=E, padx=(0,8))
        self.s_threads = Spinbox(p, from_=2, to=32, width=5)
        self.s_threads.set(8)
        self.s_threads.grid(row=0, column=3, sticky=W)

        # Opsiyon: aynı domain
        row2 = 1
        self.var_same_origin = tk.BooleanVar(value=False)
        Checkbutton(p, text="Sadece aynı domaindeki görseller", variable=self.var_same_origin).grid(row=row2, column=0, columnspan=2, sticky=W, pady=(8,0))

        # Filtre: sadece sorunlular
        row3 = 2
        self.var_only_bad = tk.BooleanVar(value=True)
        Checkbutton(p, text="Sadece sorunlu sayfaları/görselleri göster (NoImage, BrokenImage)", variable=self.var_only_bad, command=self.apply_filter).grid(row=row3, column=0, columnspan=3, sticky=W, pady=(8,0))

        # Butonlar
        self.btn_scan = Button(p, text="Taramayı Başlat", bootstyle=SUCCESS, command=self.start_scan)
        self.btn_scan.grid(row=3, column=2, pady=12, sticky=EW)

        self.btn_stop = Button(p, text="Durdur", bootstyle=DANGER, command=self.stop_scan)
        self.btn_stop.grid(row=3, column=3, pady=12, sticky=W)

        self.btn_export = Button(p, text="CSV Dışa Aktar (Görünen)", bootstyle=PRIMARY, command=self.export_csv)
        self.btn_export.grid(row=3, column=4, pady=12, sticky=W)

    def _build_center(self):
        # Paned window: üstte tablo, altta log
        self.paned = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        self.paned.pack(fill=BOTH, expand=True, padx=15, pady=(0,10))

        # Özet
        summary_frame = Frame(self.paned, padding=(0,0,0,10))
        self.paned.add(summary_frame, weight=0)
        self.var_summary = tk.StringVar(value="Toplam: 0 | Resimsiz Sayfa: 0 | Kırık Görsel: 0")
        Label(summary_frame, textvariable=self.var_summary, bootstyle=INFO).pack(anchor=W)

        # Tablo
        table_frame = Frame(self.paned, padding=0)
        self.paned.add(table_frame, weight=3)

        cols = ("page_url","image_url","flags","detail","error")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=180 if c!="page_url" else 320, anchor=tk.W, stretch=True)
        self.tree.column("page_url", width=360, stretch=True)

        self.tree.tag_configure("bad", background="#40252a")
        self.tree.tag_configure("ok", background="")

        ysb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        xsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=ysb.set, xscroll=xsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        def on_dbl_click(event):
            item = self.tree.focus()
            if not item:
                return
            vals = self.tree.item(item, "values")
            url = vals[1] or vals[0]
            if url:
                webbrowser.open(url)
        self.tree.bind("<Double-1>", on_dbl_click)

        # Log
        log_frame = Frame(self.paned, padding=(0,10,0,0))
        self.paned.add(log_frame, weight=2)
        Label(log_frame, text="Anlık Log", bootstyle=INFO).pack(anchor=W, pady=(0,6))
        self.log_txt = scrolledtext.ScrolledText(log_frame, height=10, wrap="word", state="disabled")
        self.log_txt.pack(fill=BOTH, expand=True)

    def _build_status(self):
        s = Frame(self.root, padding=(15,0,15,15))
        s.pack(fill=X, side=BOTTOM)
        self.var_status = tk.StringVar(value="Hazır")
        self.lbl_status = Label(s, textvariable=self.var_status, anchor=W)
        self.lbl_status.pack(side=LEFT)

        self.pb = ttk.Progressbar(s, mode="determinate")
        self.pb.pack(side=RIGHT, fill=X, expand=True, padx=(10,0))

    # -------------- yardımcılar --------------
    def _append_log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}"
        self.log_lines.append(line)
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", line + "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def _refresh_summary(self):
        total_rows = len(self.all_rows)
        noimg = sum(1 for r in self.all_rows if r.get("flags") == "NoImage")
        broken = sum(1 for r in self.all_rows if r.get("flags") == "BrokenImage")
        self.var_summary.set(f"Toplam: {total_rows} | Resimsiz Sayfa: {noimg} | Kırık Görsel: {broken}")

    def _redraw_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.rows.clear()

        only_bad = self.var_only_bad.get()
        data = list(self.all_rows)
        # sorunluları üstte göster
        order_score = {"BrokenImage": 0, "NoImage": 1, "": 2}
        data.sort(key=lambda r: order_score.get(r.get("flags",""), 9))

        for r in data:
            is_bad = (r.get("flags") in ("NoImage", "BrokenImage"))
            if only_bad and not is_bad:
                continue
            values = (
                r.get("page_url",""),
                r.get("image_url",""),
                r.get("flags",""),
                r.get("detail",""),
                r.get("error",""),
            )
            tag = "bad" if is_bad else "ok"
            self.tree.insert("", "end", values=values, tags=(tag,))
            self.rows.append({
                "page_url": values[0],
                "image_url": values[1],
                "flags": values[2],
                "detail": values[3],
                "error": values[4],
            })

    def apply_filter(self):
        self._redraw_table()

    # -------------- iş akışı --------------
    def start_scan(self):
        sitemap = self.e_sitemap.get().strip()
        if not sitemap:
            messagebox.showwarning("Uyarı", "Lütfen bir Sitemap URL girin.")
            return
        try:
            threads = int(self.s_threads.get())
        except Exception:
            messagebox.showerror("Hata", "İş parçacığı sayısı sayı olmalıdır.")
            return

        self.clear_table()
        self.all_rows.clear()
        self._refresh_summary()

        self.stop_event.clear()
        self.var_status.set("Sitemap okunuyor...")
        self._append_log(f"Sitemap alınıyor: {sitemap}")
        self.root.update_idletasks()

        def run():
            pages = parse_sitemap(sitemap)
            if not pages:
                self.queue.put(("status", "Sitemap'ta sayfa bulunamadı."))
                self.queue.put(("log", f"Sayfa bulunamadı veya sitemap okunamadı: {sitemap}"))
                return
            self.queue.put(("status", f"{len(pages)} sayfa bulundu. Tarama başlıyor..."))
            self.queue.put(("log", f"{len(pages)} sayfa bulundu."))
            self.queue.put(("progress_max", len(pages)))
            origin = urlparse(sitemap).netloc

            processed = 0
            def worker(page_url: str):
                logs = []
                logs.append(f"Sayfa işleniyor: {page_url}")
                results = []
                try:
                    resp = fetch(page_url, timeout=30)
                    resp.raise_for_status()
                    imgs = find_images_in_html(page_url, resp.text)
                    logs.append(f"Hedef görsel sayısı: {len(imgs)}")
                except Exception as e:
                    results.append({"page_url": page_url, "image_url": "", "flags": "NoImage", "detail": "", "error": f"FetchError: {e}"})
                    logs.append(f"Hata: sayfa alınamadı -> {e}")
                    imgs = []

                if imgs:
                    for u in imgs:
                        # aynı domain filtresi
                        if self.var_same_origin.get():
                            host = urlparse(u).netloc
                            if host and host != origin:
                                logs.append(f"Atlandı (farklı domain): {u}")
                                continue
                        ok, detail = verify_image_url(u)
                        if ok:
                            results.append({"page_url": page_url, "image_url": u, "flags": "", "detail": detail, "error": ""})
                        else:
                            results.append({"page_url": page_url, "image_url": u, "flags": "BrokenImage", "detail": detail, "error": ""})
                else:
                    results.append({"page_url": page_url, "image_url": "", "flags": "NoImage", "detail": "", "error": ""})
                return results, logs

            with ThreadPoolExecutor(max_workers=threads) as ex:
                futs = [ex.submit(worker, p) for p in pages]
                for f in as_completed(futs):
                    if self.stop_event.is_set():
                        break
                    try:
                        items, logs = f.result()
                        for logline in logs:
                            self.queue.put(("log", logline))
                        for r in items:
                            self.queue.put(("row_all", r))
                    except Exception as e:
                        self.queue.put(("status", f"Hata: {e}"))
                        self.queue.put(("log", f"Beklenmeyen hata: {e}"))
                    processed += 1
                    self.queue.put(("progress", processed))

            self.queue.put(("status", "Tarama tamamlandı."))
            self.queue.put(("log", "Tarama tamamlandı."))

        threading.Thread(target=run, daemon=True).start()

    def stop_scan(self):
        if not self.stop_event.is_set():
            self.stop_event.set()
            self.var_status.set("Durduruluyor...")
            self._append_log("Durdurma sinyali gönderildi.")

    def export_csv(self):
        if not self.rows:
            messagebox.showinfo("Bilgi", "Dışa aktarılacak veri yok (görünen veri yok).")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyası", "*.csv")],
            title="CSV olarak kaydet (görünen satırlar)"
        )
        if not path:
            return
        cols = ["page_url","image_url","flags","detail","error"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in self.rows:
                    w.writerow(r)
            messagebox.showinfo("Tamam", f"CSV kaydedildi:\n{path}")
            self._append_log(f"CSV kaydedildi: {path}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
            self._append_log(f"CSV kaydedilemedi: {e}")

    def clear_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.rows.clear()
        self.pb["value"] = 0
        self.var_status.set("Hazır")
        self._refresh_summary()

    def _drain_queue(self):
        try:
            while True:
                msg, payload = self.queue.get_nowait()
                if msg == "status":
                    self.var_status.set(str(payload))
                elif msg == "progress_max":
                    self.pb["maximum"] = int(payload)
                    self.pb["value"] = 0
                elif msg == "progress":
                    self.pb["value"] = int(payload)
                elif msg == "row_all":
                    r = payload
                    self.all_rows.append(r)
                    self._refresh_summary()
                    self._redraw_table()
                elif msg == "log":
                    self._append_log(str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
