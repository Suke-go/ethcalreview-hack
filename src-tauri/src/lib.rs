// EthicalReviewHacker — Tauri shell
//
// 役割:
//  - アプリ起動時に PyInstaller でビルドされた backend.exe を sidecar として起動
//  - 終了時に sidecar をクリーンアップ
//  - フロントエンドからの IPC コマンド `get_backend_port` で固定ポートを提供

use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// バックエンドが listen するローカルポート。
/// よく使われるポートとの衝突を避けるため少し珍しい値を選んでいる。
const BACKEND_PORT: u16 = 17500;

#[derive(Default)]
struct BackendChild(Mutex<Option<CommandChild>>);

#[tauri::command]
fn get_backend_port() -> u16 {
    BACKEND_PORT
}

/// 外部 URL を OS のデフォルトブラウザで開く。
///
/// Tauri WebView は `<a target="_blank">` を解釈しないため、外部リンクは
/// 必ずこのコマンド経由で開く必要がある。許可するスキームは http/https のみ。
#[tauri::command]
fn open_external(app: tauri::AppHandle, url: String) -> Result<(), String> {
    // 危険なスキーム (file://, javascript:, データ URL 等) を弾く
    let lower = url.to_ascii_lowercase();
    if !(lower.starts_with("http://") || lower.starts_with("https://")) {
        return Err(format!("unsupported url scheme: {}", url));
    }
    app.shell()
        .open(&url, None)
        .map_err(|e| format!("failed to open url: {}", e))
}

/// session_id が安全か (path traversal を含まないか) 確認するヘルパー。
fn is_safe_session_id(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 128
        && s.chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
}

/// バックエンドが書き出した ZIP を Downloads フォルダにコピーし、
/// エクスプローラ/Finder で選択状態にして開く。
///
/// Tauri 2 の WebView2 はプログラム的な `<a download>` クリックを
/// silent に drop する (DownloadStarting イベントのハンドラを Tauri が
/// 既定で接続していない) ため、ファイル保存は Rust 側で行う必要がある。
///
/// 前提: フロントエンド側で先に
///   GET http://127.0.0.1:17500/api/generate/download/{session_id}
/// を叩いて、バックエンドが `{ETHICS_DATA_DIR}/output/{session_id}/ethics_documents.zip`
/// にディスク書き込みを完了させていること。
#[tauri::command]
fn save_zip_to_downloads(
    app: tauri::AppHandle,
    session_id: String,
    suggested_filename: Option<String>,
) -> Result<String, String> {
    if !is_safe_session_id(&session_id) {
        return Err(format!("invalid session_id: {}", session_id));
    }

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("app_data_dir 解決失敗: {}", e))?;
    let src: PathBuf = data_dir
        .join("output")
        .join(&session_id)
        .join("ethics_documents.zip");
    if !src.exists() {
        return Err(format!(
            "ZIP がまだ生成されていません: {}",
            src.display()
        ));
    }

    let downloads = app
        .path()
        .download_dir()
        // Downloads が解決できない環境ではデスクトップ → ホーム → app_data の順でフォールバック
        .or_else(|_| app.path().desktop_dir())
        .or_else(|_| app.path().home_dir())
        .unwrap_or_else(|_| data_dir.clone());

    let filename = suggested_filename
        .filter(|s| !s.is_empty() && !s.contains('/') && !s.contains('\\'))
        .unwrap_or_else(|| format!("ethics_documents_{}.zip", session_id));
    let dst = downloads.join(&filename);

    std::fs::copy(&src, &dst)
        .map_err(|e| format!("ファイルコピー失敗 {} → {}: {}", src.display(), dst.display(), e))?;

    // OS ごとに「ファイルを選択した状態でフォルダを開く」
    #[cfg(target_os = "windows")]
    {
        // explorer.exe は /select,<path> を一引数で渡す必要がある
        std::process::Command::new("explorer.exe")
            .arg(format!("/select,{}", dst.display()))
            .spawn()
            .map_err(|e| format!("explorer 起動失敗: {}", e))?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg("-R")
            .arg(&dst)
            .spawn()
            .map_err(|e| format!("Finder reveal 失敗: {}", e))?;
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        // Linux 等: 親ディレクトリを開く (ファイル選択は対応 FM があれば後で拡張)
        if let Some(parent) = dst.parent() {
            app.shell()
                .open(parent.to_string_lossy().into_owned(), None)
                .map_err(|e| format!("dir open 失敗: {}", e))?;
        }
    }

    Ok(dst.to_string_lossy().into_owned())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendChild::default())
        .invoke_handler(tauri::generate_handler![
            get_backend_port,
            open_external,
            save_zip_to_downloads
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // ETHICS_DATA_DIR をユーザーデータディレクトリに固定
            // (sessions / output / settings.json をユーザー領域に保存)
            let data_dir = app
                .path()
                .app_data_dir()
                .expect("failed to resolve app_data_dir");
            std::fs::create_dir_all(&data_dir).ok();

            let sidecar = app
                .shell()
                .sidecar("backend")
                .expect("sidecar `backend` not declared in tauri.conf.json")
                .env("HOST", "127.0.0.1")
                .env("PORT", BACKEND_PORT.to_string())
                .env("ETHICS_DATA_DIR", data_dir.to_string_lossy().to_string());

            let (mut rx, child) = sidecar.spawn().expect("failed to spawn backend sidecar");

            // 子プロセスハンドルを保持して、終了時に kill できるようにする
            *app.state::<BackendChild>().0.lock().unwrap() = Some(child);

            // stdout/stderr を Tauri のログに流す (デバッグ用)
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            eprintln!("[backend stdout] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[backend stderr] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(payload) => {
                            eprintln!("[backend] terminated: {:?}", payload);
                            // 必要ならここでユーザーに通知する
                            let _ = handle.emit("backend-exited", payload.code);
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // 全ウィンドウ閉じる / 終了時に sidecar を kill
            if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
                if let Some(child) = app_handle
                    .state::<BackendChild>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        });
}
