from flask import Blueprint, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import uuid
from urllib.parse import urlparse
import re

downloader_bp = Blueprint('downloader', __name__)

# مجلد مؤقت للملفات المحملة
DOWNLOAD_DIR = '/tmp/q8_downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def is_valid_url(url):
    """التحقق من صحة الرابط"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_platform_from_url(url):
    """تحديد المنصة من الرابط"""
    url = url.lower()
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'tiktok.com' in url:
        return 'tiktok'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'snapchat.com' in url:
        return 'snapchat'
    else:
        return 'unknown'

def get_ydl_opts(platform, format_type, download_id):
    """إعدادات yt-dlp حسب المنصة"""
    base_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{download_id}.%(ext)s'),
        'format': 'best' if format_type == 'mp4' else 'bestaudio/best',
        'extractaudio': format_type == 'mp3',
        'audioformat': 'mp3' if format_type == 'mp3' else None,
        'audioquality': '192',
        'no_warnings': True,
        'ignoreerrors': True,
    }
    
    # إعدادات خاصة لكل منصة
    if platform == 'youtube':
        base_opts.update({
            'format': 'best[height<=720]' if format_type == 'mp4' else 'bestaudio/best',
            # تجاهل مشاكل التحقق من البوت
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_skip': ['configs', 'webpage']
                }
            },
            # إعدادات إضافية لتجنب مشاكل YouTube
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        })
    elif platform == 'instagram':
        base_opts.update({
            'format': 'best',
            # إعدادات لتجنب مشاكل Instagram
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            }
        })
    elif platform == 'tiktok':
        base_opts.update({
            'format': 'best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        })
    elif platform == 'twitter':
        base_opts.update({
            'format': 'best'
        })
        
    return base_opts

@downloader_bp.route('/download', methods=['POST'])
def download_video():
    """API لتحميل الفيديوهات"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'لم يتم إرسال بيانات'}), 400
            
        url = data.get('url', '').strip()
        format_type = data.get('format', 'mp4').lower()
        
        # التحقق من صحة الرابط
        if not url:
            return jsonify({'error': 'يرجى إدخال رابط الفيديو'}), 400
            
        if not is_valid_url(url):
            return jsonify({'error': 'الرابط غير صحيح'}), 400
            
        # تحديد المنصة
        platform = get_platform_from_url(url)
        
        # إنشاء معرف فريد للتحميل
        download_id = str(uuid.uuid4())
        
        # الحصول على إعدادات yt-dlp
        ydl_opts = get_ydl_opts(platform, format_type, download_id)
        
        # تحميل الفيديو
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # الحصول على معلومات الفيديو
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'فيديو بدون عنوان')
                duration = info.get('duration', 0)
                
                # تحميل الفيديو
                ydl.download([url])
                
                # البحث عن الملف المحمل
                downloaded_files = []
                for file in os.listdir(DOWNLOAD_DIR):
                    if file.startswith(download_id):
                        downloaded_files.append(file)
                
                if not downloaded_files:
                    return jsonify({'error': 'فشل في تحميل الفيديو'}), 500
                    
                downloaded_file = downloaded_files[0]
                file_path = os.path.join(DOWNLOAD_DIR, downloaded_file)
                file_size = os.path.getsize(file_path)
                
                return jsonify({
                    'success': True,
                    'message': 'تم تحميل الفيديو بنجاح',
                    'data': {
                        'title': title,
                        'platform': platform,
                        'format': format_type,
                        'duration': duration,
                        'file_size': file_size,
                        'download_id': download_id,
                        'filename': downloaded_file,
                        'download_url': f'/api/file/{download_id}'
                    }
                })
                
            except yt_dlp.DownloadError as e:
                error_msg = str(e)
                
                # رسائل خطأ مخصصة حسب المنصة
                if platform == 'youtube':
                    if 'Sign in to confirm' in error_msg or 'bot' in error_msg.lower():
                        return jsonify({
                            'error': 'YouTube يطلب التحقق من الهوية. جرب رابط آخر أو انتظر قليلاً ثم أعد المحاولة.',
                            'suggestion': 'يمكنك تجربة روابط من منصات أخرى مثل TikTok أو Twitter'
                        }), 429
                elif platform == 'instagram':
                    if 'rate-limit' in error_msg or 'login required' in error_msg:
                        return jsonify({
                            'error': 'Instagram يحد من التحميل. جرب رابط آخر أو انتظر قليلاً ثم أعد المحاولة.',
                            'suggestion': 'تأكد أن المنشور عام وليس خاص'
                        }), 429
                
                # رسائل خطأ عامة
                if 'Video unavailable' in error_msg:
                    return jsonify({'error': 'الفيديو غير متاح أو محذوف'}), 404
                elif 'Private video' in error_msg:
                    return jsonify({'error': 'الفيديو خاص ولا يمكن تحميله'}), 403
                elif 'Sign in to confirm your age' in error_msg:
                    return jsonify({'error': 'الفيديو مقيد بالعمر'}), 403
                else:
                    return jsonify({'error': f'خطأ في التحميل من {platform}. جرب منصة أخرى.'}), 500
                    
    except Exception as e:
        return jsonify({'error': f'خطأ في الخادم: {str(e)}'}), 500

@downloader_bp.route('/file/<download_id>', methods=['GET'])
def download_file(download_id):
    """تحميل الملف"""
    try:
        # البحث عن الملف
        downloaded_files = []
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(download_id):
                downloaded_files.append(file)
        
        if not downloaded_files:
            return jsonify({'error': 'الملف غير موجود'}), 404
            
        file_path = os.path.join(DOWNLOAD_DIR, downloaded_files[0])
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'الملف غير موجود'}), 404
            
        # تحسين اسم الملف للتحميل
        original_name = downloaded_files[0]
        # إزالة UUID من اسم الملف
        clean_name = original_name.split('.', 1)[-1] if '.' in original_name else original_name
        
        return send_file(file_path, as_attachment=True, download_name=clean_name)
        
    except Exception as e:
        return jsonify({'error': f'خطأ في تحميل الملف: {str(e)}'}), 500

@downloader_bp.route('/info', methods=['POST'])
def get_video_info():
    """الحصول على معلومات الفيديو بدون تحميل"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'لم يتم إرسال بيانات'}), 400
            
        url = data.get('url', '').strip()
        
        if not url or not is_valid_url(url):
            return jsonify({'error': 'الرابط غير صحيح'}), 400
            
        platform = get_platform_from_url(url)
        
        # إعدادات yt-dlp للحصول على المعلومات فقط
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'title': info.get('title', 'فيديو بدون عنوان'),
                        'description': info.get('description', ''),
                        'duration': info.get('duration', 0),
                        'view_count': info.get('view_count', 0),
                        'uploader': info.get('uploader', ''),
                        'platform': platform,
                        'thumbnail': info.get('thumbnail', ''),
                        'formats_available': ['mp4', 'mp3']
                    }
                })
                
            except yt_dlp.DownloadError as e:
                return jsonify({'error': f'خطأ في جلب المعلومات: {str(e)}'}), 500
                
    except Exception as e:
        return jsonify({'error': f'خطأ في الخادم: {str(e)}'}), 500

@downloader_bp.route('/supported-platforms', methods=['GET'])
def get_supported_platforms():
    """قائمة المنصات المدعومة"""
    platforms = [
        {
            'name': 'TikTok',
            'id': 'tiktok', 
            'icon': 'tiktok',
            'formats': ['mp4', 'mp3'],
            'status': 'ممتاز'
        },
        {
            'name': 'Twitter/X',
            'id': 'twitter',
            'icon': 'twitter',
            'formats': ['mp4', 'mp3'],
            'status': 'ممتاز'
        },
        {
            'name': 'Snapchat',
            'id': 'snapchat',
            'icon': 'snapchat',
            'formats': ['mp4', 'mp3'],
            'status': 'ممتاز'
        },
        {
            'name': 'YouTube',
            'id': 'youtube',
            'icon': 'youtube',
            'formats': ['mp4', 'mp3'],
            'status': 'محدود - قد يحتاج تحقق'
        },
        {
            'name': 'Instagram',
            'id': 'instagram',
            'icon': 'instagram',
            'formats': ['mp4', 'mp3'],
            'status': 'محدود - قد يحتاج تحقق'
        }
    ]
    
    return jsonify({
        'success': True,
        'platforms': platforms,
        'note': 'YouTube و Instagram قد يحتاجان تحقق إضافي أحياناً'
    })

@downloader_bp.route('/health', methods=['GET'])
def health_check():
    """فحص حالة الخدمة"""
    return jsonify({
        'status': 'healthy',
        'message': 'خدمة تحميل الفيديوهات تعمل بشكل طبيعي',
        'version': '1.1.0',
        'platforms': {
            'tiktok': 'ممتاز',
            'twitter': 'ممتاز', 
            'snapchat': 'ممتاز',
            'youtube': 'محدود',
            'instagram': 'محدود'
        }
    })

