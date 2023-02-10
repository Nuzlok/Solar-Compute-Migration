import http.server
import json
import mimetypes
import os
import shutil
import time
import urllib
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
from socketserver import ThreadingMixIn

from template import header, script


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def _get_item_list(self, path, recursive=False):
        assert path.is_dir()
        items = []
        dir_path = "**/" if recursive else ""
        for ext in ['mp4', 'jpg', 'png', 'gif', 'jpeg']:
            items.extend([str(f) for f in path.glob(f'{dir_path}*.{ext}')])
        items.sort()
        return items

    def do_POST(self):
        """Serve a POST request."""
        data_string = self.rfile.read(int(self.headers.get('content-length')))
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        # Retrieve video and image files in dir_path
        dir_path = data_string.decode('utf-8')
        items = self._get_item_list(Path(dir_path))

        return_info = []
        for item_path in items:
            item_name = item_path.rsplit('/', 1)[-1]
            mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(item_path)))
            return_info.append({'name': item_name, 'path': item_path})
        self.wfile.write(json.dumps(return_info).encode('utf-8'))

    def do_HEAD(self):
        """Serve a HEAD request."""
        if f := self.send_head():
            f.close()

    def do_GET(self):
        """Serve a GET request."""
        if self.path == '/':
            # Retrieve video and image files recursively
            items = self._get_item_list(Path(self._logdir), recursive=self._recursive)

            # Group files based on the parent dirs
            item_names = defaultdict(list)
            for item_path in items:
                if len(item_path.rsplit('/', 1)) > 1:
                    dir_name, item_name = item_path.rsplit('/', 1)
                else:
                    dir_name = ''
                    item_name = item_path
                item_names[dir_name].append((item_path, item_name))

            # Build the html response with the file list
            head_html = header.replace('max-height: 320px;',  f'max-height: {self._max_height}px;').replace('max-width: 320px;', f'max-width: {self._max_width}px;')
            script_html = script.replace('max_length = 30',   f'max_length = {self._max_file_name_length}')

            html = [f'<!DOCTYPE html><html>{head_html}<body>']
            for dir_name in item_names.keys():
                html.append(f'<button class="accordion">{dir_name}[{len(item_names[dir_name])} items]</button><div class="panel"></div>')
            html.append(f'{script_html}</body></html>')

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('\n'.join(html).encode())
        else:
            # Send a raw file (video or image)
            if f := self.send_head():
                if self._range:
                    s, e = self._range
                    buf_size = 64 * 1024
                    f.seek(s)
                    while True:
                        buf = f.read(min(buf_size, e - f.tell() + 1))
                        if not buf:
                            break
                        self.wfile.write(buf)
                else:
                    shutil.copyfileobj(f, self.wfile)
                f.close()

    # Code from https://gist.github.com/UniIsland/3346170 and
    # https://gist.github.com/shivakar/82ac5c9cb17c95500db1906600e5e1ea
    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = urllib.parse.unquote(os.getcwd() + self.path)
        ext = ''
        if '.' in path:
            ext = '.' + path.rsplit('.')[-1].lower()
            if ext not in self.extensions_map:
                ext = ''
        ctype = self.extensions_map[ext]

        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            return self.send_error(404, "File not found")

        fs = os.fstat(f.fileno())
        file_size = content_size = fs[6]

        if 'Range' in self.headers:  # Support byte-range requests
            s, e = self.headers['Range'].strip().split('=')[1].split('-')
            try:
                s = int(s) if s else file_size - int(e)
                e = int(e) if e else file_size - 1
                if s >= file_size or e >= file_size or s > e:
                    raise ValueError
            except ValueError:
                return self.send_error(400, "Invalid range")
            self._range = (s, e)
            content_size = e - s + 1
            self.send_response(206)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Range', f'bytes {s}-{e}/{file_size}')
        else:
            self._range = None
            self.send_response(200)

        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(content_size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    if mimetypes.inited is False:  # Initialize extension maps
        mimetypes.init()  # Try to read system mime.types
    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({'': 'application/octet-stream'})


class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """Handle requests in a separate thread."""
    pass


def str2bool(v):
    return v.lower() == 'true'


def main():
    parser = ArgumentParser(prog='videoboard_v2', description='A simple server for streaming media files')
    parser.add_argument('--port', type=int, default=8000, help='port number.')
    parser.add_argument('--logdir', type=str, default='.', help='directory where videoboard will look for videos and images.')
    parser.add_argument('--height', type=int, default=320, help='maximum height of image/video.')
    parser.add_argument('--width', type=int, default=320, help='maximum width of image/video.')
    parser.add_argument('--file_name_length', type=int, default=30, help='maximum length of file name.')
    parser.add_argument('--recursive', type=str2bool, default=True, choices=[True, False], help='search files recursively.')
    parser.add_argument('--bind_ip', type=str, default='', help='The address to bind the server to.')
    args = parser.parse_args()

    os.chdir(args.logdir)  # Change directory to prevent access to directories other than logdir

    class RequestHandlerWithArgs(RequestHandler):
        _logdir = '.'
        _max_height = args.height
        _max_width = args.width
        _max_file_name_length = args.file_name_length
        _recursive = args.recursive

    try:
        server = ThreadedHTTPServer((args.bind_ip, args.port), RequestHandlerWithArgs)
        print(f'Run videoboard server on <IP:{args.bind_ip}, port:{args.port}>')
        server.serve_forever()
    except KeyboardInterrupt:
        print('Close server')
        server.server_close()


if __name__ == '__main__':
    main()
