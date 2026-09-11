import base64
import time
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def extract_rekhta_pdf(url, output_pdf):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument(r"--user-data-dir=C:\tmp-chrome-session") 
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)
    
    print(f"\nLoading book: {url}")
    driver.get(url)
    
    try:
        total_elem = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ebookTotalPageCount")))
        detected_pages = int(total_elem.text.strip())
    except Exception:
        detected_pages = 297

    print("\n" + "="*55)
    print("ACTION REQUIRED:")
    print("1. Log in to Rekhta if prompted.")
    print("2. Close ALL ads or popups on the screen.")
    print("3. Ensure you are looking at PAGE 1.")
    print("="*55 + "\n")
    
    print(f"Detected {detected_pages} pages.")
    user_input = input("Press ENTER to use this count, or type a new exact number: ").strip()
    total_pages = int(user_input) if user_input.isdigit() else detected_pages
    
    print(f"\n[ SYSTEM LOCKED ] Extracting {total_pages} pages using Strict Sibling Pacing...")
    
    images = []
    seen_b64 = set()
    extracted_count = 0
    stuck_counter = 0
    
    def get_visible_canvases():
        return driver.execute_script("""
            var windowWidth = window.innerWidth;
            var canvases = document.querySelectorAll("canvas.actualmage");
            var result = [];
            canvases.forEach(function(c) {
                var rect = c.getBoundingClientRect();
                var centerX = rect.left + (rect.width / 2);
                var style = window.getComputedStyle(c);
                if (centerX > 0 && centerX < windowWidth && rect.width > 0 && 
                    parseFloat(style.opacity) > 0.8 && style.visibility !== 'hidden' && style.display !== 'none') {
                    var b64 = c.toDataURL('image/jpeg', 1.0).substring(23);
                    result.push({ x: rect.left, b64: b64 });
                }
            });
            return result;
        """)

    def nuke_overlays():
        driver.execute_script("""
            var popups = document.querySelectorAll('.modal, .overlay, [role="dialog"], .popup');
            popups.forEach(function(p) { p.remove(); });
            
            var allDivs = document.querySelectorAll('div');
            allDivs.forEach(function(el) {
                var style = window.getComputedStyle(el);
                if ((style.position === 'fixed' || style.position === 'absolute') && parseInt(style.zIndex) > 10) {
                    if (!el.querySelector('canvas')) { 
                        el.style.display = 'none';
                    }
                }
            });
            document.body.style.overflow = 'auto';
        """)

    def click_next_page():
        nuke_overlays()
        body = driver.find_element(By.TAG_NAME, 'body')
        window_width = driver.execute_script("return window.innerWidth;")
        x_offset = int(-(window_width / 2) + 40)
        actions.reset_actions()
        # Added .pause(0.5) to physically prevent double-clicking
        actions.move_to_element_with_offset(body, x_offset, 0).click().pause(0.5).perform()

    while extracted_count < total_pages:
        time.sleep(4) 
        
        nuke_overlays()
        canvas_data = get_visible_canvases()
        
        # Check if ANY new pages are in this scan
        has_new = any(d['b64'] not in seen_b64 for d in canvas_data)
        
        if has_new:
            # SIBLING DELAY: Wait 2 extra seconds to ensure the 2nd page finishes loading before saving!
            time.sleep(2)
            
            # Re-scan the screen now that both pages are guaranteed to be fully loaded
            canvas_data = get_visible_canvases()
            canvas_data.sort(key=lambda item: item['x'], reverse=True)
            
            for data in canvas_data:
                if data['b64'] not in seen_b64:
                    seen_b64.add(data['b64'])
                    img = Image.open(BytesIO(base64.b64decode(data['b64']))).convert('RGB')
                    images.append(img)
                    extracted_count += 1
                    print(f"Successfully extracted page {extracted_count}/{total_pages}")
                    
                    if extracted_count >= total_pages:
                        break
                        
            if extracted_count >= total_pages:
                break
            
            stuck_counter = 0
            time.sleep(1) # Cooldown before turning
            click_next_page()
            
        else:
            stuck_counter += 1
            print(f"-> Waiting for network to catch up... ({stuck_counter}/10)")
            
            if stuck_counter % 3 == 0:
                print("-> Retrying page-turn click...")
                click_next_page()
                
            if stuck_counter >= 10:
                print("\n[!] CRITICAL: Network timeout or absolute end of book reached.")
                break

    driver.quit()
    
    # --- THE SALVAGE PROTOCOL ---
    print("\n" + "="*55)
    if len(images) == total_pages:
        print(f"[ SUCCESS ] Perfect extraction. All {total_pages} pages accounted for.")
        print(f"Building PDF: '{output_pdf}'...")
        images[0].save(output_pdf, save_all=True, append_images=images[1:], resolution=100.0)
        print("Done! Check your folder.")
    elif len(images) > 0:
        print(f"[ INCOMPLETE ] Target: {total_pages} pages. Extracted: {len(images)} pages.")
        print("Reason: Rekhta metadata might be wrong (the book actually ended early), or network timed out.")
        
        choice = input(f"Do you want to save the {len(images)} pages we successfully extracted anyway? (y/n): ").strip().lower()
        if choice == 'y':
            print(f"Building PDF: '{output_pdf}'...")
            images[0].save(output_pdf, save_all=True, append_images=images[1:], resolution=100.0)
            print("Salvage successful! Check your folder.")
        else:
            print("PDF discarded.")
    else:
        print("FAILURE: No pages extracted.")
    print("="*55)

if __name__ == "__main__":
    book_url = input("Paste Rekhta Link Here:\n").strip()
    parsed_url = urlparse(book_url)
    slug = parsed_url.path.strip('/').split('/')[-1]
    
    # Uses .title() as requested to capitalize every word's first letter
    generated_filename = slug.replace('-', ' ').title() + ".pdf"
    
    extract_rekhta_pdf(book_url, generated_filename)
