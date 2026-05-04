import os
import shutil

def organize_music_files(root_directory):
    for root, dirs, files in os.walk(root_directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(('.mp3', '.flac','.wav')):#如果有其他格式音乐文件自行添加，不涉及任何文件内容修改，因此可以适配任何格式
                try:
                    file_name = os.path.splitext(file)[0]
                    infom = file_name.split('=') #如果前文没有使用等号请自行更改
                    album_name = infom[1].strip()

                    album_directory = os.path.join(root_directory, album_name)
                    if not os.path.exists(album_directory):
                        os.makedirs(album_directory)

                    new_file_name = file_name.replace('=', '-')+os.path.splitext(file)[1]
                    destination_path = os.path.join(album_directory, new_file_name)
                    shutil.move(file_path, destination_path)
                except:
                    print(f"Error processing file: {file}")
                    continue
if __name__ == '__main__':
    # 调用函数，指定根目录
    root_directory = r"your_media_path"
    organize_music_files(root_directory)
