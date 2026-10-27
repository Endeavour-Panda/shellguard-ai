"""Generate an ordinary URL QR code; never encode credentials."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
import qrcode
import qrcode.image.svg

parser=argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--output-dir',type=Path,default=Path('artifacts/public'))
args=parser.parse_args()
parsed=urlsplit(args.url)
if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
    parser.error('Use a plain HTTPS URL without credentials, query or fragment')
args.output_dir.mkdir(parents=True,exist_ok=True)
qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4)
qr.add_data(args.url)
qr.make(fit=True)
qr.make_image(fill_color='black',back_color='white').save(args.output_dir/'shellguard-qr.png')
qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(args.output_dir/'shellguard-qr.svg')
(args.output_dir/'link.json').write_text(json.dumps({'url':args.url,'access':'Requires existing web username/password; server must remain running. Temporary Gradio links expire and may change after restart.'},ensure_ascii=False,indent=2))
print(args.output_dir/'shellguard-qr.png')
