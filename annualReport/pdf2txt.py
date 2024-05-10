# -*- coding: utf-8 -*-
import os, re, shutil, tempfile, mimetypes, subprocess, logging
from distutils import spawn  # py2 compat

from subprocess import Popen, PIPE, STDOUT, CalledProcessError, TimeoutExpired
from subprocess import run
from pathlib import Path

logger = logging.getLogger(__name__)

def get_languages():

    def lang_error(output):
        logger.warning = (
            "Tesseract failed to report available languages.\n"
            "Output from Tesseract:\n"
            "-----------\n"
        )
        return
    logger.debug("get lang called")
    args_tess = ['tesseract', '--list-langs']
    try:
        proc = run(
            args_tess,
            text=True,
            stdout=PIPE,
            stderr=STDOUT,
            check=True,
        )
        output = proc.stdout
    except CalledProcessError as e:
        raise EnvironmentError(lang_error(e.output)) from e

    for line in output.splitlines():
        if line.startswith('Error'):
            raise EnvironmentError(lang_error(output))
    _header, *rest = output.splitlines()
    langlist = {lang.strip() for lang in rest}
    return '+'.join(map(str, langlist))

def orc_to_text(path, temp_dir=None):
    """Wraps Tesseract OCR with auto language model.
    Parameters
    ----------
    path : str
        path of to pdf in PDF, JPG or PNG format

    Returns
    -------
    extracted_str : str
        returns extracted text from image
    """

    # Check for dependencies. Needs Tesseract and Imagemagick installed.
    if not spawn.find_executable("tesseract"): raise EnvironmentError("tesseract not installed.")
    if not spawn.find_executable("convert"): raise EnvironmentError("imagemagick not installed.")

    language = get_languages()
    logger.debug(f"tesseract language arg is, {language}")
    timeout = 180
    mt = mimetypes.guess_type(path)
    if mt[0] == "application/pdf":
        # tesseract does not support pdf files, pre-processing is needed.
        logger.debug("PDF file detected, start pre-processing by converting to png")
        # convert the (multi-page) pdf file to a 300dpi png
        convert = [
            "convert",
            "-units",
            "PixelsPerInch",
            "-density",
            "300",
            path,
            "-depth",
            "6",
            "-alpha",
            "off",
            "-colorspace",
            "gray",
            "-resample",
            "300x300",
            "-blur",
            "0x2.5",
            "-contrast-stretch",
            "1x90%",
            "-append",
            "png:-",
        ]
        p1 = Popen(convert, stdout=PIPE)
        tess_input = "stdin"
        stdin = p1.stdout
    else:
        tess_input = path
        stdin = None

    inputfile = Path(path)
    filename = inputfile.stem

    tmp_dir = temp_dir or tempfile.mkdtemp(suffix='p2t')
    logger.debug(f"temp dir is, *{tmp_dir}*")

    tess_cmd = [
        "tesseract",
        "-l",
        language,
        "--oem",
        "3",
        "--psm",
        "6",
        "-c",
        "preserve_interword_spaces=1",
        "-c",
        "textonly_pdf=1",
        tess_input,
        os.path.join(tmp_dir, filename),
        "pdf",
        "txt"
    ]

    logger.debug(f"Calling tesseract with args, {tess_cmd}")
    p2 = Popen(tess_cmd, stdin=stdin, stdout=PIPE)

    # Wait for p2 to finish generating the pdf
    try:
        p2.wait(timeout=timeout)
    except TimeoutExpired:
        p2.kill()
        logger.warning("tesseract took too long to OCR - skipping")

    pdftotext_cmd = ["pdftotext", "-layout", "-enc", "UTF-8", os.path.join(tmp_dir, f"{filename}.pdf"), "-",]

    logger.debug(f"Calling pdfttext with, {pdftotext_cmd}")
    p3 = Popen(pdftotext_cmd, stdin=p2.stdout, stdout=PIPE)
    out = ""
    try:
        out, err = p3.communicate(timeout=timeout)
    except TimeoutExpired:
        p3.kill()
        logger.warning("pdftotext took too long - skipping")

    if temp_dir is None: shutil.rmtree(tmp_dir)
    return out
def to_text(path, encoding='UTF-8',images_too=False):
    # page break b'\x0c'
    if not spawn.find_executable("pdftotext"): raise EnvironmentError("pdftotext not installed. Can be downloaded from https://poppler.freedesktop.org/")
    cmd = ["pdftotext", "-q", "-layout", "-enc", encoding, path, "-"]
    logger.debug(f"Calling pdfttext with, {cmd}")
    all_text_bytes, err = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()

    tmp_dir = tempfile.mkdtemp(suffix='p2t')
    logger.debug(f"temp dir is, *{tmp_dir}*")
    pages = None
    if images_too or len(all_text_bytes) < 10:
        cmd = ["pdfimages", "-p", "-png", path, tmp_dir+"/"]
        logger.debug(f"Calling pdfimages with, {cmd}")
        e, err = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()
        images = [each for each in os.listdir(tmp_dir) if each.endswith('.png')]
        pages = [p.decode(encoding) for p in all_text_bytes.split(b'\x0c')]
        for image in images:
            page_image = int(re.search(r"-(\d\d\d)-\d\d\d", image).group(1))
            page = pages[page_image-1]
            image_txt = orc_to_text(os.path.join(tmp_dir, image), tmp_dir).decode(encoding)
            if len(image_txt) > 5:
                if '\n\n\n\n' in page:
                    pages[page_image-1] = page.replace('\n\n\n\n', f"\n\n{image_txt}\n\n", 1)
                else: pages[page_image-1] = f"{page}\n\n{image_txt}"
    shutil.rmtree(tmp_dir)
    return '\x0c'.join(pages) if pages else all_text_bytes.decode(encoding)
