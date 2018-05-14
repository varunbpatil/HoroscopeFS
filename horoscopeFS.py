import os
import sys
import bs4
import fuse
import tempfile
import requests
import textwrap

# Name must match the class that implements it.
# Each of these will be a directory under the mountpoint.
horoscope_sites = ['Astrosage', 'Astroyogi', 'AstroyogiCareer', 'IndianAstrology2000']

# Each of these will be a file under the directory
# corresponding to the horoscope site.
horoscope_types = ['daily', 'weekly', 'monthly']

class Req(object):
    def __init__(self):
        super().__init__()

    def _get(self, url, timeout=30):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            return soup
        except:
            return None

class Astrosage(Req):
    """Horoscopes from www.astrosage.com"""

    def __init__(self, sunsign, moonsign):
        super().__init__()

        base_url = "http://www.astrosage.com/horoscope/"
        self.horoscope = {}
        for horoscope_type in horoscope_types:
            url = "{}/{}-{}-horoscope.asp"
            url = url.format(base_url, horoscope_type, moonsign)
            self.horoscope[horoscope_type] = self._parse_html(url, horoscope_type)

    def _parse_html(self, url, horoscope_type):
        soup = self._get(url)
        if soup:
            if horoscope_type == "daily":
                html_class_attr = "ui-large-content-box"
            else:
                html_class_attr = "ui-sign-content-box"
            content = soup.find(class_=html_class_attr).text
            content = textwrap.fill(content.strip()) + "\n"
            return content.encode()
        else:
            return b"Not available\n"

class Astroyogi(Req):
    """Horoscopes from www.astroyogi.com"""

    def __init__(self, sunsign, moonsign):
        super().__init__()

        base_url = "https://www.astroyogi.com/horoscopes"
        self.horoscope = {}
        for horoscope_type in horoscope_types:
            url = "{}/{}/{}-free-horoscope.aspx"
            url = url.format(base_url, horoscope_type, sunsign)
            self.horoscope[horoscope_type] = self._parse_html(url)

    def _parse_html(self, url):
        soup = self._get(url)
        if soup:
            content = soup.find(id="ContentPlaceHolder1_LblPrediction").contents[0]
            content = textwrap.fill(content.strip()) + "\n"
            return content.encode()
        else:
            return b"Not available\n"

class AstroyogiCareer(Req):
    """Career horoscopes from www.astroyogi.com"""

    def __init__(self, sunsign, moonsign):
        super().__init__()

        base_url = "https://www.astroyogi.com/horoscopes"
        self.horoscope = {}
        for horoscope_type in horoscope_types:
            url = "{}/{}/{}-career-horoscope.aspx"
            url = url.format(base_url, horoscope_type, sunsign)
            self.horoscope[horoscope_type] = self._parse_html(url)

    def _parse_html(self, url):
        soup = self._get(url)
        if soup:
            content = soup.find(id="ContentPlaceHolder1_LblPrediction").contents[0]
            content = textwrap.fill(content.strip()) + "\n"
            return content.encode()
        else:
            return b"Not available\n"

class IndianAstrology2000(Req):
    """Horoscopes from www.indianastrology2000.com"""

    def __init__(self, sunsign, moonsign):
        super().__init__()

        base_url = "https://www.indianastrology2000.com/horoscope"
        self.horoscope = {}
        for horoscope_type in horoscope_types:
            if horoscope_type == "daily":
                url = "{}/index.php?zone=3&sign={}"
                url = url.format(base_url, moonsign)
                self.horoscope[horoscope_type] = self._parse_html(url)
            elif horoscope_type == "weekly":
                # No weekly horoscope available.
                self.horoscope[horoscope_type] = b"Not available\n"
            elif horoscope_type == "monthly":
                url = "{}/{}-monthly-horoscope.html"
                url = url.format(base_url, moonsign)
                self.horoscope[horoscope_type] = self._parse_html(url)

    def _parse_html(self, url):
        soup = self._get(url)
        if soup:
            content = soup.find(class_="horoscope-sign-content-block").text
            content = textwrap.fill(content.strip()) + "\n"
            return content.encode()
        else:
            return b"Not available\n"

class HoroscopeFS(fuse.Operations):
    """Virtual filesystem for aggregating horoscopes from various websites"""

    def __init__(self, sunsign, moonsign):
        print("Initializing...")

        # Get default stats for an empty directory and empty file.
        # The temporary directory and file are automatically deleted.
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.stat_dict_dir = \
                    self._convert_stat_to_dict(os.lstat(tmp_dir))

        with tempfile.NamedTemporaryFile() as tmp_file:
            self.stat_dict_file = \
                    self._convert_stat_to_dict(os.lstat(tmp_file.name))

        self.sunsign = sunsign
        self.moonsign = moonsign
        self.dot_dirs = ['.', '..']

        # Construct objects for each of the horoscope sites.
        self.horoscope_objs = {}
        self.current_module = sys.modules[__name__]
        for site in horoscope_sites:
            obj = getattr(self.current_module, site)(self.sunsign, self.moonsign)
            self.horoscope_objs[site] = obj

        print("Ready")

    # Given a 'stat_result' object, convert it into a Python dictionary.
    def _convert_stat_to_dict(self, stat_result):
        stat_keys = ('st_atime', 'st_ctime', 'st_gid', 'st_mode',
                     'st_mtime', 'st_nlink', 'st_size', 'st_uid')

        return dict((key, getattr(stat_result, key)) for key in stat_keys)

    # Get the size of the file corresponding to the given path.
    # Path is a string of the form /<horoscope_site>/<horoscope_type>
    def _get_file_size_from_path(self, path):
        horoscope_site, horoscope_type = path.split(os.sep)[1:3]
        horoscope_obj = self.horoscope_objs[horoscope_site]
        return len(horoscope_obj.horoscope[horoscope_type])

    # Read data from the given file path.
    # Path is a string of the form /<horoscope_site>/<horoscope_type>
    def _read_data_from_path(self, path, length, offset):
        horoscope_site, horoscope_type = path.split(os.sep)[1:3]
        horoscope_obj = self.horoscope_objs[horoscope_site]
        return horoscope_obj.horoscope[horoscope_type][offset : offset+length]

    def getattr(self, path, fh=None):
        if any(map(path.endswith, horoscope_sites)):
            # For directories corresponding to the horoscope websites,
            # return the default stats for directory.
            return self.stat_dict_dir
        elif any(map(path.endswith, horoscope_types)):
            # For files corresponding to the horoscope types,
            # return the stats for the file with st_size set appropriately.
            stat = dict(self.stat_dict_file) # Create a copy before modifying
            stat['st_size'] = self._get_file_size_from_path(path)
            return stat
        else:
            # For all other files/directories, return the stats from the OS.
            return self._convert_stat_to_dict(os.lstat(path))

    def readdir(self, path, fh):
        if any(map(path.endswith, horoscope_sites)):
            # Each horoscope website directory contains one file for each
            # horoscope type.
            return self.dot_dirs + horoscope_types
        else:
            # Top level directory (mountpoint) contains one directory for each
            # horoscope website.
            return self.dot_dirs + horoscope_sites

    def read(self, path, length, offset, fh):
        return self._read_data_from_path(path, length, offset)

def main(mountpoint, sunsign, moonsign):
    fuse.FUSE(HoroscopeFS(sunsign, moonsign),
              mountpoint,
              nothreads=True,
              foreground=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2].lower(), sys.argv[3].lower())
