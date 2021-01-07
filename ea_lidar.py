import os
import uuid
import shutil
import glob
import time
import tempfile
import geopandas as gp
from zipfile import ZipFile
import argparse

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import chromedriver_binary

import urllib.request
from tqdm.auto import tqdm


def download_tile(zipf, download=False, product='LIDAR Point Cloud', 
                  verbose=True, download_dir=False, headerless=True):
    
    options = Options()
    options.headless = headerless
    driver = webdriver.Chrome(chromedriver_binary.chromedriver_filename, options=options)
    driver.get("https://environment.data.gov.uk/DefraDataDownload/?Mode=survey")

    wait = WebDriverWait(driver, 50)
    if verbose: print('...waiting for page to load')
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#fileid")))

    webElem = driver.find_element_by_css_selector("#fileid")
    webElem.send_keys([zipf])
    if verbose: print('...waiting for shapefile to load')
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grid-item-container")))

    getTiles = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grid-item-container")))
    time.sleep(2)
    getTiles.click()

    if verbose: print('...waiting for available products to load')

    # wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#productSelect')))

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "option[value='LIDAR Composite DTM']")),
               message='There are no EA products for this area')

    prodElem = driver.find_element_by_css_selector('#productSelect')
    available = [x.get_attribute('value') for x in prodElem.find_elements_by_tag_name("option")]
    if product not in available:
        print('product not available')
    else:
        xP = '//*[@id="productSelect"]/option[{}]'.format(available.index(product) + 1)

        webElem = driver.find_element_by_xpath(xP)
        webElem.click()
        linki = 1
        while True:
            try:
                download_el = driver.find_element_by_css_selector('.data-ready-container > a:nth-child({})'.format(linki))
                href = download_el.get_attribute("href")
                download_url(href, 
                             os.path.join(os.path.split(zipf)[0] if not download_dir else download_dir, 
                                          href.split('/')[-1]))
                linki += 1
            except:
                if verbose: print(linki - 1, 'files downloaded')
                driver.close()
                break

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_url(url, output_path):
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
    

if __name__ == '__main__':
    
    # some arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('extent', type=str, nargs=1, help='path to extent')
    parser.add_argument('--odir', type=str, nargs=1, help='directory to store tiles')
    parser.add_argument('--product', '-p', type=str, default='LIDAR Composite DTM',
                        help='choose from "LIDAR Composite DSM", "LIDAR Composite DTM", \
                                          "LIDAR Point Cloud", "LIDAR Tiles DSM", \
                                          "LIDAR Tiles DTM", "National LIDAR Programme DSM", \
                                          "National LIDAR Programme DTM", "National LIDAR Programme First Return DSM", \
                                          "National LIDAR Programme Point Cloud"')
    parser.add_argument('--open-chrome', action='store_false', help='opne chrome instance i.e. do not run headless')
    parser.add_argument('--verbose', action='store_true', help='print something')
    args = parser.parse_args()
    args.extent = args.extent[0]
    
    print(args.product)
    
    # temp directory
    tmp_d = tempfile.mkdtemp()
    tmp_n = str(uuid.uuid4())
    
    with ZipFile(os.path.join(tmp_d, tmp_n + '.zip'), 'w') as zipObj: 
        [zipObj.write(f) for f in glob.glob(os.path.splitext(args.extent)[0] + '*')]
        
    if args.verbose: print('zip saved to:',  os.path.join(tmp_d, tmp_n + '.zip'))
        
    download_tile(os.path.join(tmp_d, tmp_n + '.zip'),
                  product=args.product,
                  headerless=args.open_chrome,
                  verbose=args.verbose)
    
    



