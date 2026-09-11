import streamlit as st
import base64
import time
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

st.set_page_config(page_title="Rekhta PDF Extractor", page_icon="📚")
st.title("📚 Rekhta PDF Extractor")

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # CRITICAL SECURITY BYPASS: Linux Chrome requires a dummy user-data-dir to disable web security
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--user-data-dir=/tmp/chrome-session")
    
    driver = webdriver.Chrome(options=options)
    return driver

url = st.text_input("Paste Rekhta Link Here:")
target_pages = st.number_input("Pages to extract (Check Rekhta for total pages):", min_value=1, max_value=1000, value=50)

if st.button("Start Extraction") and url:
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()
    
    driver = get_driver()
    actions = ActionChains(driver)
    
    status_text.text("Loading book (waiting 5 seconds for initialization)...")
    driver.get(url)
    time.sleep(5)
    
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
                    if (!el.querySelector('canvas')) { el.style.display = 'none'; }
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
        actions.move_to_element_with_offset(body, x_offset, 0).click().pause(0.5).perform()

    with log_container:
        while extracted_count < target_pages:
            time.sleep(4) 
            
            nuke_overlays()
            canvas_data = get_visible_canvases()
            
            # SIBLING DELAY LOGIC: Check if ANY new pages are in this scan
            has_new = any(d['b64'] not in seen_b64 for d in canvas_data)
            
            if has_new:
                # Wait 2 extra seconds to ensure the 2nd page finishes loading before saving
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
                        
                        st.write(f"Successfully extracted page {extracted_count}/{target_pages}")
                        progress_bar.progress(min(extracted_count / target_pages, 1.0))
                        
                        if extracted_count >= target_pages:
                            break
                            
                if extracted_count >= target_pages:
                    break
                
                stuck_counter = 0
                time.sleep(1) # Cooldown before turning
                click_next_page()
                
            else:
                stuck_counter += 1
                status_text.text(f"Waiting for cloud network... ({stuck_counter}/10)")
                
                if stuck_counter % 3 == 0:
                    click_next_page()
                
                if stuck_counter >= 10:
                    st.warning(f"⚠️ Extraction stopped early at {extracted_count} pages. The server network timed out, or this is the physical end of the book.")
                    break

    driver.quit()
    
    # --- PDF GENERATION & DOWNLOAD ---
    if len(images) > 0:
        status_text.text(f"Compiling PDF with {len(images)} pages...")
        
        pdf_buffer = BytesIO()
        images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:], resolution=100.0)
        pdf_data = pdf_buffer.getvalue()
        
        parsed_url = urlparse(url)
        slug = parsed_url.path.strip('/').split('/')[-1]
        
        # Formats the filename to Title Case
        filename = slug.replace('-', ' ').title() + ".pdf"
        
        if len(images) == target_pages:
            status_text.success("Extraction Complete!")
        else:
            status_text.success("Salvage Complete! (PDF compiled with the pages we managed to grab).")
        
        st.download_button(
            label="Download PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf"
        )
    else:
        status_text.error("No pages were extracted.")
