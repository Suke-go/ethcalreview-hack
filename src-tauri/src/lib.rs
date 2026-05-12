// EthicalReviewHacker — Tauri shell
//
// 役割:
//  - アプリ起動時に PyInstaller でビルドされた backend.exe を sidecar として起動
//  - 終了時に sidecar をクリーンアップ
//  - フロントエンドからの IPC コマンド `get_backend_port` で固定ポートを提供

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendChild::default())
        .invoke_handler(tauri::generate_handler![get_backend_port])
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
