import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json

import sys
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector

class HtmlConverter():
    def __init__(self, saved_json_page_folder, all_html_paths=[]):
        self.saved_json_page_folder = saved_json_page_folder
        self.all_html_paths = all_html_paths

        self.full_help_content_json_file_path = os.path.join(self.saved_json_page_folder, "full_help_content.json")
        if os.path.exists(self.full_help_content_json_file_path):
            os.remove(self.full_help_content_json_file_path)
        self.n_files_per_batch = 15
        self.chat_api_connector = ChatAPIConnector()

    def _extract_images(self, tag):
        """
        Extract all image sources from the given BeautifulSoup tag.
        """
        images = []
        for img in tag.find_all("img"):
            src = img.get("src")
            if src:
                images.append(src)
        return images

    def _parse_html_sections(self, html_content):
        """
        根據實際文件結構進行解析：
        - 優先從 <title> 中取得文件標題，如果沒有，再找 <h1>
        - 尋找內容區塊：這裡假設用 id="main" 或 class="content" 的 div，如果都沒有，再退回使用 <section>
        同時，從每個區塊提取圖片（img）的 src 屬性。
        """
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 嘗試從 <title> 提取標題
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "No Title"
        
        # 尋找內容區塊
        container = soup.find(id="main")
        if container is None:
            container = soup.find(class_="content")
        if container is None:
            # 如果找不到，就退回使用整個文件
            container = soup

        sections = []
        # 如果 container 裡有 <section>，以 section 為單位；否則就根據 <h2> 分段
        section_tags = container.find_all("section")
        if section_tags:
            for section in section_tags:
                heading_tag = section.find(["h2", "h3", "h4"])
                heading = heading_tag.get_text(strip=True) if heading_tag else "No Heading"
                text = section.get_text(separator=" ", strip=True)
                images = self.extract_images(section)
                sections.append({
                    "heading": heading,
                    "text": text,
                    "images": images,
                    "original_html": str(section)
                })
        else:
            # 如果沒有 <section> 標籤，嘗試以 <h2> 為分界
            h2_tags = container.find_all("h2")
            if h2_tags:
                for h2 in h2_tags:
                    heading = h2.get_text(strip=True)
                    content = ""
                    # Initialize a temporary container for siblings to later extract images.
                    temp_container = []
                    for sibling in h2.find_next_siblings():
                        if sibling.name == "h2":
                            break
                        temp_container.append(sibling)
                        content += sibling.get_text(" ", strip=True) + " "
                    # Create a new BeautifulSoup object from the siblings to extract images
                    temp_soup = BeautifulSoup("".join(str(tag) for tag in temp_container), "html.parser")
                    images = self._extract_images(temp_soup)
                    sections.append({
                        "heading": heading,
                        "text": content.strip(),
                        "images": images,
                    })
            else:
                # 若都無法分段，就把整個 container 當作一個區塊
                text = container.get_text(separator=" ", strip=True)
                images = self._extract_images(container)
                sections.append({
                    "heading": "Content",
                    "text": text,
                    "images": images,
                    "original_html": str(container)
                })
        
        return title, sections

    def _html_to_json(self, chunk_paths):
        all_data = []
        # 直接遍歷傳入的檔案路徑列表
        for file_path in chunk_paths:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            title, sections = self._parse_html_sections(html_content)
            filename = os.path.basename(file_path)
            all_data.append({
                "file": filename,
                "title": title,
                "sections": sections
            })
        return all_data

    def _change_all_html_to_n_json_files(self):
        # 3. 以每self.n_files_per_batch個檔案為一組進行處理，並將結果存放到對應的資料夾中
        for i in range(0, len(self.all_html_paths), self.n_files_per_batch):
            chunk_paths = self.all_html_paths[i:i+self.n_files_per_batch]
            folder_num = i // self.n_files_per_batch + 1
            json_data = self._html_to_json(chunk_paths)
            output_filename = os.path.join(self.saved_json_page_folder, f"batch_{folder_num:03d}.json")
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

    def _get_prompt(self, file):
        # read the file
        with open(file, "r", encoding="utf-8") as f:
            json_content = f.read()
        prompt = '''
The data in the section is too disorganized. Please maintain the original sections while consolidating similar items into blocks for clarity. Ensure that the summary retains all the original information. Provide an English version and keep the 'file' intact. The final output should be in JSON format. 

Here is the example of JSON Format:
{
  "blocks": [
    {
      "block_title": "",
      "sections": [
        {
          "heading": "",
          "summary": "",
          "images": [ ]
        },
        {
          "heading": "",
          "summary": "",
          "images": [
          ]
        }
      ]
    },
}

''' + json_content
        
        return prompt


    def _ask_llm_to_summarize(self, prompt):
        system_role_msg = "Process the provided input data by preserving its original sections. Consolidate similar items into blocks for clarity, ensuring that all original information is retained in the summary. Translate the content into English while keeping the 'file' field intact. The final output must strictly adhere to the provided JSON format."
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg)

    def _write_full_json_file(self, content):
        # append content to the full json file
        with open(self.full_help_content_json_file_path, "a", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

    def process(self):
        self._change_all_html_to_n_json_files(self.all_html_paths)
        for file in self.saved_json_page_folder:
            prompt = self._get_prompt(file)
            content = self._ask_llm_to_summarize(prompt)
            self._write_full_json_file(content)


class HelpRetriever():
    def __init__(self, saved_html_page_folder, allowed_prefix):
        self.allowed_prefix = allowed_prefix
        self.saved_html_page_folder = saved_html_page_folder
        self.output_saved_html_page_folder_list = []

    def _get_links(self):
        """
        Get all the links of the help pages.
        args:
            None
        return:
            list: a list of all the links of the help pages.
        """
        # Here is an example for PDR mac, please provide your own product help page links.
        html_files = [
            '02_00_00_powerdirector_launcher.html', '03_00_00_the_pdr_workspace.html', '03_01_00-powerdirector-modules.html', 
            '03_02_00_rooms.html', '03_02_01_media_rooms.html', '03_02_02_intro_video_room.html', '03_02_03_title_room.html', 
            '03_02_04_transition_room.html', '03_02_05_effectroom.html', '03_02_06_pip_objects_room.html', 
            '03_02_07_particle_room.html', '03_02_08_audio_mixing_room.html', '03_02_09_voice-over.html', 
            '03_02_11_subtitle_room.html', '03_03_00_library_window.html', '03_03_01_explorer_view.html', 
            '03_03_02_searching_for_media_i.html', '03_03_03_filter_media.html', '03_03_04_library_win_view.html', 
            '03_03_05_library_menu.html', '03_04_00_expanding_workspace.html', '03_04_01_undock_pw.html', 
            '03_05_00_preview_window.html', '03_05_01_library_preview_win.html', '03_05_02_project_preview_win.html', 
            '03_05_04_preview_controls.html', '03_05_05_display_preview_options.html', '03_05_02_take_snapshot.html', 
            '03_06_00_editing_workspace.html', '03_06_01_timeline_view.html', '04_00_00_pdr_projects.html', 
            '04_01_00_settingprojectaspectratio.html', '04_02_00_exporting_projects.html', '04_03_00_reusing_powerdirector.html', 
            '04_03_01_nested_projects.html', '04_05_00_cldrive_projects.html', '05_00_00_importing.html', 
            '05_01_0_importing_media.html', '05_01_01_support_file_formats.html', '05_01_04_importing_powerdirect.html', 
            '05_02_0_downloading_media.html', '05_02_02_download_gi.html', '05_02_01_download_music.html', 
            '05_02_03_downloading_from_dz_clc.html', '07_00_00_arranging_media_in_workspace.html', '07_01_00_adding_media.html', 
            '07_01_01_adding_video_clips_an.html', '07_01_02_adding_color_boards_a.html', '07_02_00_adding_audio_clips.html', 
            '07_02_01_syncing_audio.html', '07_03_00_syncing_by_audio.html', '07_00_00_video_intro_templates.html', 
            '07_01_00_add_ivt_favorites.html', '07_02_00_my_profile.html', '07_03_00_editing_templates_ivd.html', 
            '07_03_01_replacing_media.html', '07_03_02_select_range.html', '07_03_03_crop_media.html', '07_03_04_flip.html', 
            '07_03_04_applylut.html', '07_03_04_add-edit_text.html', '07_03_05_adding_images.html', '07_03_06_adding_vo.html', 
            '07_03_07_edit_ivt_bgm.html', '07_03_08_ivt_designer_settings.html', '07_03_09_produce.html', 
            '06_00_00_powerdirector_plug-in.html', '06_09_00_video-collage.html', '06_09_01_creating_a_video-coll.html', 
            '06_09_02_savie_share_collage.html', '08_00_00_editing_your_media.html', '08_01_00_splitting_a_clip.html', 
            '08_02_00_trimming.html', '08_02_01_trimming_a_video_clip.html', '08_02_02_trimming_audio.html', 
            '08_02_03_manual_trim.html', '08_03_00_setting_media_duration.html', '08_04_00_unlinking_clips.html', 
            '08_06_00_adjusting_vc_ar.html', '08_07_00_stretching_images.html', '08_08_00_croppin_images.html', 
            '08_09_00_resizemoverotate.html', '08_09_01_move_resize_media.html', '08_09_02_rotate_media.html', 
            '08_10_00_creating_shape.html', '08_11_00_fix_and_enhance.html', '08_12_00_utilizing_keyframes_o.html', 
            '08_12_01_adding_and_editing_ke.html', '08_13_00_adding_fade_in_out_to.html', '08_14_00_muting_clips.html', 
            '08_15_00_editing_audio.html', '08_15_01_editing_audio_ae.html', '09_00_00_using_the_tools.html', 
            '09_01_00_crop_rotate.html', '09_02_00_pan_zoom.html', '09_04_00_adjusting_video_speed.html', 
            '09_05_00_smart_fit_duration.html', '09_07_00_audiospeed.html', '09_06_00_reverse_video-audio.html', 
            '09_08_00_mt.html', '09_08_01_tracking_objects_in_v.html', '09_08_02_adding_and_editing_tr.html', 
            '09_08_03_adding_tracking_effec.html', '09_09_00-blending_clips_tl.html', '09_10_00_audio_ducking.html', 
            '13_00_00_creating_titles.html', '13_01_00-types-of-title-effect.html', '13_01_01-standard-2d-title-eff.html', 
            '13_01_02_motion_graphics_title.html', '13_01_03_title_effects_sound.html', '13_02_00_modifying-in-td_basic.html', 
            '13_02_01_title_zoom_tools.html', '13_02_02_adding-text.html', '13_02_03_modifying_title_ef.html', 
            '13_02_04_modifying_text_prop.html', '13_02_05_set_tt_length.html', '13_02_06_saving_and_sharing_ti.html', 
            '13_03_00_modifying_in_td.html', '13_03_01_title_zoom_tools.html', '13_03_02_adding_text_stuff_.html', 
            '13_03_03_modifying_title_ef.html', '13_03_04_modifying_text_proper.html', '13_03_05_applying_ttmotion.html', 
            '13_03_06_adding_motion_to_tt.html', '13_03_07_utilizing_te_keyframes.html', '13_03_08_saving_and_sharing_ti.html', 
            '15_00_00_using_transitions.html', '15_01_00_adding_transitions_to.html', '15_02_00_adding_transitions_be.html', 
            '15_03_00_using_audio_transitio.html', '15_04_00_setting_transition_be.html', '15_05_00_modifying_transition_settings.html', 
            '10_00_00_adding_videos_effects.html', '10_04_01_ai_object_selection.html', '10_04_00_blending_effect.html', 
            '10_03_00_cluts.html', '10_01_00_adding_video_effects.html', '10_01_01_modify_video_effects.html', 
            '11_00_00_creating_pip.html', '11_01_00_adding_pip_objects.html', '11_01_01-types-of-pip-objects.html', 
            '11_01_02_creating_custom_pip_o.html', '11_06_00_pip_designles.html', '18_01_00_auto_transcribe_sub.html', 
            '18_02_00_adding_subtitles.html', '18_03_00_importing_subtitles.html', '18_04_00_editing_subtitles.html', 
            '18_04_01_syncing_subtitles.html', '18_05_00_exporting_subtitles.html', '19_00_00_producing_your_project.html', 
            '19_01_00_producing_range.html', '19_02_00_produce_window.html', '19_01_00_profile_analyzer.html', 
            '19_02_01_outtputting_file.html', '19_02_02_image_sequence.html', '19_02_03_audio_file.html', 
            '19_02_05_uploading.html', '96_00_00_preferences.html', '96_01_00_general_preferences.html', 
            '96_02_00_editing_preferences.html', '96_03_00_file_preferences.html', '96_03_01_cache_preferences.html', 
            '96_04_00_display_preferences.html', '96_06_00_project_preferences.html', '96_07_00_produce_preferences.html', 
            '96_09_00_confirmation_preferences.html', '96_11_00_cld_preferences.html', '96_12_00_ip_preferences.html', 
            '97_00_00_hotkeys.html', '97_01_00_default_hotkeys.html', '97_01_01_amb_hotkeys.html', 
            '97_01_02_system_hotkeys.html', '97_01_04_edit_hotkeys.html', '97_01_05_workspace_hotkeys.html', 
            '97_01_06_designer_hotkeys.html', '97_00_00_hotkeys.html', '98_00_00_appendix.html', '98_01_00_how_to_pop_search.html', 
            '98_01_01_cl_install_cam.html', '98_01_02_watermarks.html', '98_01_03_install_effects_stock.html', '98_01_04_dl_ge.html', 
            '98_01_04_dl_meta.html', '98_01_05_how_to_trim.html', '98_01_07_convert_pds.html', '98_01_07_produce.html', 
            '98_01_12_how_to_rotate.html', '98_01_13_green_screen.html', '98_01_15_audio.html', '98_01_17_speed.html', 
            '98_01_18_masks.html', '98_01_19_luts.html', '98_02_00_svrt_when.html'
        ]
        links = []
        for html_file in html_files:
            links.append(self.allowed_prefix + html_file)
        return links

    def _fetch_page(self, link):
        """
        Read the content of the webpage and extract the title and the specified content block (div#hmpagebody_scroller) with BeautifulSoup.
        Also correct the relative path of the images to absolute path to avoid the images not showing.
        args:
            link: str, the link of the webpage.
        return:
            dict: a dictionary with the title and the content of the webpage.
        """
        try:
            response = requests.get(link)
            response.encoding = 'utf-8'
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.text.strip() if title_tag else link

            # 只抓取指定區塊內的內容
            content_div = soup.find("div", id="hmpagebody_scroller")
            if content_div:
                # 轉換所有圖片的 src 為絕對路徑
                for img in content_div.find_all("img"):
                    src = img.get("src")
                    if src:
                        absolute_src = urljoin(link, src)
                        img["src"] = absolute_src
                content = content_div.decode_contents()
            else:
                content = html

            return {"title": title, "content": content}
        except Exception as e:
            print(f"讀取 {link} 時發生錯誤: {e}")
            return {"title": link, "content": "讀取內容錯誤。"}

    def _output_individual_page(self, page_content, url):
        """輸出單個頁面的 HTML 檔案，檔名根據 URL 最後部分命名"""
        os.makedirs(self.saved_html_page_folder, exist_ok=True)
        filename = url.split("/")[-1]
        filepath = os.path.join(self.saved_html_page_folder, filename)
        html_content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            f"<title>{page_content['title']}</title>",
            "</head>",
            "<body>",
            f"<h2>{page_content['title']}</h2>",
            f"<div>{page_content['content']}</div>",
            "</body>",
            "</html>"
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(html_content))

    def _get_all_html_path(self):
        all_html_paths = []
        for folder in self.output_saved_html_page_folder_list:
            html_files = [f for f in os.listdir(folder) if f.lower().endswith('.html')]
            for f in html_files:
                all_html_paths.append(os.path.join(folder, f))
        return all_html_paths
    

    def process(self):
        links = self._get_links()
        for link in links:
            page_content = self._fetch_page(link)
            self._output_individual_page(page_content, link)
        
        all_html_paths = self._get_all_html_path()
        return all_html_paths
        

class TaskExecutor:
    def __init__(self, path_settings, allowed_prefix): 
        self.allowed_prefix = allowed_prefix
        self.saved_html_page_folder = path_settings["saved_html_page_folder"]
        self.saved_json_page_folder = path_settings["saved_json_page_folder"]

        self.help_retriever = HelpRetriever(self.saved_html_page_folder, self.saved_json_page_folder, self.allowed_prefix)
        self.html_converter = HtmlConverter(self.saved_json_page_folder)

    def extract_process(self):
        # Get all online help pages and save them to local html files.
        all_html_paths = self.help_retriever._get_all_html_path()
        self.html_converter.all_html_paths = all_html_paths

        # Convert all html files to json files and ask LLM to summarize the content.
        self.html_converter.process()
        

if __name__ == "__main__":
    path_settings = {
        "saved_html_page_folder": "html_pages",
        "saved_json_page_folder": "json_pages"
    }
    allowed_prefix = "https://help.cyberlink.com/stat/help/powerdirector/2024/mac/enu/"
    task_executor = TaskExecutor(path_settings, allowed_prefix)
    task_executor.extract_process()
