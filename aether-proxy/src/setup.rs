//! Interactive TUI for configuring aether-proxy.
//!
//! Launched via `aether-proxy setup [path]`.  Presents a full-screen form
//! backed by ratatui where the user can navigate fields, edit values, and
//! save to a TOML config file.

use std::io;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use crossterm::execute;
use crossterm::terminal::{self, EnterAlternateScreen, LeaveAlternateScreen};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;
use ratatui::Terminal;

use crate::config::ConfigFile;

/// Column width reserved for the field label (chars).
const LABEL_WIDTH: usize = 22;

// ── Field types ──────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq)]
enum FieldKind {
    Text,
    Secret,
    Number,
    Bool,
    PortList,
    LogLevel,
}

struct Field {
    label: &'static str,
    key: &'static str,
    value: String,
    kind: FieldKind,
    required: bool,
    help: &'static str,
}

// ── App state ────────────────────────────────────────────────────────────────

#[derive(PartialEq)]
enum Mode {
    Normal,
    Editing,
}

struct App {
    fields: Vec<Field>,
    selected: usize,
    mode: Mode,
    edit_buffer: String,
    edit_cursor: usize, // char index
    config_path: PathBuf,
    modified: bool,
    message: Option<(String, Instant, bool)>, // (text, when, is_error)
    scroll_offset: usize,
    saved_once: bool,
}

impl App {
    fn new(config_path: PathBuf) -> Self {
        Self {
            fields: vec![
                Field {
                    label: "Aether URL",
                    key: "aether_url",
                    value: String::new(),
                    kind: FieldKind::Text,
                    required: true,
                    help: "Aether 服务器 URL (如 https://aether.example.com)",
                },
                Field {
                    label: "Management Token",
                    key: "management_token",
                    value: String::new(),
                    kind: FieldKind::Secret,
                    required: true,
                    help: "Aether 管理 API Token (ae_xxx)",
                },
                Field {
                    label: "HMAC Key",
                    key: "hmac_key",
                    value: String::new(),
                    kind: FieldKind::Secret,
                    required: true,
                    help: "HMAC-SHA256 签名密钥，用于代理请求认证",
                },
                Field {
                    label: "Listen Port",
                    key: "listen_port",
                    value: "18080".into(),
                    kind: FieldKind::Number,
                    required: true,
                    help: "代理服务监听端口",
                },
                Field {
                    label: "Public IP",
                    key: "public_ip",
                    value: String::new(),
                    kind: FieldKind::Text,
                    required: false,
                    help: "节点公网 IP (留空则自动检测)",
                },
                Field {
                    label: "Node Name",
                    key: "node_name",
                    value: "proxy-01".into(),
                    kind: FieldKind::Text,
                    required: true,
                    help: "节点名称，用于在 Aether 后台识别",
                },
                Field {
                    label: "Node Region",
                    key: "node_region",
                    value: String::new(),
                    kind: FieldKind::Text,
                    required: false,
                    help: "节点区域标识 (如 ap-northeast-1)",
                },
                Field {
                    label: "Heartbeat Interval",
                    key: "heartbeat_interval",
                    value: "30".into(),
                    kind: FieldKind::Number,
                    required: true,
                    help: "心跳上报间隔 (秒)",
                },
                Field {
                    label: "Allowed Ports",
                    key: "allowed_ports",
                    value: "80, 443, 8080, 8443".into(),
                    kind: FieldKind::PortList,
                    required: true,
                    help: "允许代理的目标端口，逗号分隔",
                },
                Field {
                    label: "Timestamp Tolerance",
                    key: "timestamp_tolerance",
                    value: "300".into(),
                    kind: FieldKind::Number,
                    required: true,
                    help: "HMAC 时间戳容差窗口 (秒)",
                },
                Field {
                    label: "Log Level",
                    key: "log_level",
                    value: "info".into(),
                    kind: FieldKind::LogLevel,
                    required: true,
                    help: "日志级别 — Enter 切换: trace / debug / info / warn / error",
                },
                Field {
                    label: "Log JSON",
                    key: "log_json",
                    value: "false".into(),
                    kind: FieldKind::Bool,
                    required: true,
                    help: "是否以 JSON 格式输出日志 — Enter 切换",
                },
            ],
            selected: 0,
            mode: Mode::Normal,
            edit_buffer: String::new(),
            edit_cursor: 0,
            config_path,
            modified: false,
            message: None,
            scroll_offset: 0,
            saved_once: false,
        }
    }

    // ── Config ↔ fields ──────────────────────────────────────────────────

    fn load_from_file(&mut self) {
        if let Ok(cfg) = ConfigFile::load(&self.config_path) {
            self.apply_config(&cfg);
        }
    }

    fn apply_config(&mut self, cfg: &ConfigFile) {
        for field in &mut self.fields {
            let val: Option<String> = match field.key {
                "aether_url" => cfg.aether_url.clone(),
                "management_token" => cfg.management_token.clone(),
                "hmac_key" => cfg.hmac_key.clone(),
                "listen_port" => cfg.listen_port.map(|v| v.to_string()),
                "public_ip" => cfg.public_ip.clone(),
                "node_name" => cfg.node_name.clone(),
                "node_region" => cfg.node_region.clone(),
                "heartbeat_interval" => cfg.heartbeat_interval.map(|v| v.to_string()),
                "allowed_ports" => cfg.allowed_ports.as_ref().map(|p| {
                    p.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(", ")
                }),
                "timestamp_tolerance" => cfg.timestamp_tolerance.map(|v| v.to_string()),
                "log_level" => cfg.log_level.clone(),
                "log_json" => cfg.log_json.map(|v| v.to_string()),
                _ => None,
            };
            if let Some(v) = val {
                field.value = v;
            }
        }
    }

    fn to_config(&self) -> ConfigFile {
        let get = |key: &str| -> Option<String> {
            self.fields
                .iter()
                .find(|f| f.key == key)
                .map(|f| f.value.clone())
                .filter(|v| !v.is_empty())
        };

        ConfigFile {
            aether_url: get("aether_url"),
            management_token: get("management_token"),
            hmac_key: get("hmac_key"),
            listen_port: get("listen_port").and_then(|v| v.parse().ok()),
            public_ip: get("public_ip"),
            node_name: get("node_name"),
            node_region: get("node_region"),
            heartbeat_interval: get("heartbeat_interval").and_then(|v| v.parse().ok()),
            allowed_ports: get("allowed_ports").map(|v| {
                v.split(',')
                    .filter_map(|s| s.trim().parse().ok())
                    .collect()
            }),
            timestamp_tolerance: get("timestamp_tolerance").and_then(|v| v.parse().ok()),
            log_level: get("log_level"),
            log_json: get("log_json").and_then(|v| v.parse().ok()),
        }
    }

    fn save(&mut self) -> anyhow::Result<()> {
        let cfg = self.to_config();
        cfg.save(&self.config_path)?;
        self.modified = false;
        self.saved_once = true;
        self.message = Some((
            format!("✓ 已保存到 {}", self.config_path.display()),
            Instant::now(),
            false,
        ));
        Ok(())
    }

    // ── Scrolling ────────────────────────────────────────────────────────

    fn ensure_visible(&mut self, visible_rows: usize) {
        if visible_rows == 0 {
            return;
        }
        if self.selected < self.scroll_offset {
            self.scroll_offset = self.selected;
        } else if self.selected >= self.scroll_offset + visible_rows {
            self.scroll_offset = self.selected - visible_rows + 1;
        }
    }

    // ── Key handling ─────────────────────────────────────────────────────

    /// Returns `true` when the app should exit.
    fn handle_key(&mut self, key: KeyEvent) -> bool {
        // Expire old messages
        if let Some((_, when, _)) = &self.message {
            if when.elapsed() > Duration::from_secs(4) {
                self.message = None;
            }
        }

        match self.mode {
            Mode::Normal => self.handle_normal(key),
            Mode::Editing => {
                self.handle_edit(key);
                false
            }
        }
    }

    fn handle_normal(&mut self, key: KeyEvent) -> bool {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => return true,
            KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                if let Err(e) = self.save() {
                    self.message = Some((format!("✗ {}", e), Instant::now(), true));
                }
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.selected = self.selected.saturating_sub(1);
            }
            KeyCode::Down | KeyCode::Char('j') => {
                if self.selected + 1 < self.fields.len() {
                    self.selected += 1;
                }
            }
            KeyCode::Home => self.selected = 0,
            KeyCode::End => self.selected = self.fields.len() - 1,
            KeyCode::Enter | KeyCode::Char(' ') => {
                let field = &self.fields[self.selected];
                match field.kind {
                    FieldKind::Bool => {
                        let toggled = if field.value == "true" { "false" } else { "true" };
                        self.fields[self.selected].value = toggled.into();
                        self.modified = true;
                    }
                    FieldKind::LogLevel => {
                        const LEVELS: &[&str] =
                            &["trace", "debug", "info", "warn", "error"];
                        let idx = LEVELS.iter().position(|l| *l == field.value).unwrap_or(2);
                        self.fields[self.selected].value =
                            LEVELS[(idx + 1) % LEVELS.len()].into();
                        self.modified = true;
                    }
                    _ => {
                        self.edit_buffer = field.value.clone();
                        self.edit_cursor = self.edit_buffer.chars().count();
                        self.mode = Mode::Editing;
                    }
                }
            }
            KeyCode::Tab => {
                // Quick save shortcut
                if let Err(e) = self.save() {
                    self.message = Some((format!("✗ {}", e), Instant::now(), true));
                }
            }
            _ => {}
        }
        false
    }

    fn handle_edit(&mut self, key: KeyEvent) {
        match key.code {
            KeyCode::Esc => {
                // Cancel — discard changes to this field
                self.mode = Mode::Normal;
            }
            KeyCode::Enter => {
                if self.validate_edit() {
                    self.fields[self.selected].value = self.edit_buffer.clone();
                    self.modified = true;
                    self.mode = Mode::Normal;
                } else {
                    self.message =
                        Some(("✗ 格式无效".into(), Instant::now(), true));
                }
            }
            KeyCode::Backspace => {
                if self.edit_cursor > 0 {
                    self.edit_cursor -= 1;
                    let byte = self.char_byte_pos(self.edit_cursor);
                    self.edit_buffer.remove(byte);
                }
            }
            KeyCode::Delete => {
                if self.edit_cursor < self.edit_buffer.chars().count() {
                    let byte = self.char_byte_pos(self.edit_cursor);
                    self.edit_buffer.remove(byte);
                }
            }
            KeyCode::Left => {
                self.edit_cursor = self.edit_cursor.saturating_sub(1);
            }
            KeyCode::Right => {
                let len = self.edit_buffer.chars().count();
                if self.edit_cursor < len {
                    self.edit_cursor += 1;
                }
            }
            KeyCode::Home => self.edit_cursor = 0,
            KeyCode::End => self.edit_cursor = self.edit_buffer.chars().count(),
            KeyCode::Char(c) => {
                let byte = self.char_byte_pos(self.edit_cursor);
                self.edit_buffer.insert(byte, c);
                self.edit_cursor += 1;
            }
            _ => {}
        }
    }

    fn validate_edit(&self) -> bool {
        let kind = self.fields[self.selected].kind;
        let buf = &self.edit_buffer;
        match kind {
            FieldKind::Number => buf.is_empty() || buf.parse::<u64>().is_ok(),
            FieldKind::PortList => {
                buf.is_empty()
                    || buf
                        .split(',')
                        .all(|s| s.trim().is_empty() || s.trim().parse::<u16>().is_ok())
            }
            _ => true,
        }
    }

    /// Byte offset of the char at `char_idx`.
    fn char_byte_pos(&self, char_idx: usize) -> usize {
        self.edit_buffer
            .char_indices()
            .nth(char_idx)
            .map(|(i, _)| i)
            .unwrap_or(self.edit_buffer.len())
    }
}

// ── Rendering ────────────────────────────────────────────────────────────────

fn ui(f: &mut Frame, app: &mut App) {
    let area = f.area();

    // Outer block
    let title = if app.modified {
        " Aether Proxy Setup [*] "
    } else {
        " Aether Proxy Setup "
    };

    let outer = Block::default()
        .borders(Borders::ALL)
        .title(title)
        .title_alignment(ratatui::layout::Alignment::Center)
        .border_style(Style::default().fg(Color::Cyan));

    let inner = outer.inner(area);
    f.render_widget(outer, area);

    // Split: fields | footer
    let chunks = Layout::vertical([Constraint::Min(1), Constraint::Length(4)]).split(inner);

    let fields_area = chunks[0];
    let footer_area = chunks[1];

    render_fields(f, app, fields_area);
    render_footer(f, app, footer_area);
}

fn render_fields(f: &mut Frame, app: &mut App, area: Rect) {
    let visible = area.height as usize;
    app.ensure_visible(visible);

    let mut lines: Vec<Line> = Vec::new();

    for (i, field) in app.fields.iter().enumerate() {
        if i < app.scroll_offset || i >= app.scroll_offset + visible {
            continue;
        }

        let selected = i == app.selected;
        let indicator = if selected { " ▸ " } else { "   " };

        let label_style = if selected {
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::DarkGray)
        };

        let padded_label = format!("{:<width$}", field.label, width = LABEL_WIDTH);

        // Value display
        let (value_text, value_style) = if app.mode == Mode::Editing && selected {
            (
                app.edit_buffer.clone(),
                Style::default().fg(Color::Yellow),
            )
        } else {
            field_display(field)
        };

        lines.push(Line::from(vec![
            Span::styled(indicator, label_style),
            Span::styled(padded_label, label_style),
            Span::raw("  "),
            Span::styled(value_text, value_style),
        ]));
    }

    let paragraph = Paragraph::new(lines);
    f.render_widget(paragraph, area);

    // Cursor position while editing
    if app.mode == Mode::Editing {
        let row_in_view = app.selected - app.scroll_offset;
        // prefix: 3 (indicator) + LABEL_WIDTH + 2 (gap) = 27
        let prefix: u16 = 3 + LABEL_WIDTH as u16 + 2;
        let cx = area.x + prefix + app.edit_cursor as u16;
        let cy = area.y + row_in_view as u16;
        if cx < area.x + area.width && cy < area.y + area.height {
            f.set_cursor_position((cx, cy));
        }
    }
}

/// Returns (display_text, style) for a field in normal mode.
fn field_display(field: &Field) -> (String, Style) {
    if field.value.is_empty() {
        let text = if field.required {
            "(必填)".into()
        } else {
            "—".into()
        };
        let color = if field.required {
            Color::Red
        } else {
            Color::DarkGray
        };
        return (text, Style::default().fg(color));
    }

    match field.kind {
        FieldKind::Secret => (
            "•".repeat(field.value.len().min(20)),
            Style::default().fg(Color::White),
        ),
        FieldKind::Bool => {
            if field.value == "true" {
                ("✓ 开启".into(), Style::default().fg(Color::Green))
            } else {
                ("✗ 关闭".into(), Style::default().fg(Color::DarkGray))
            }
        }
        FieldKind::LogLevel => {
            let color = match field.value.as_str() {
                "trace" => Color::Magenta,
                "debug" => Color::Blue,
                "info" => Color::Green,
                "warn" => Color::Yellow,
                "error" => Color::Red,
                _ => Color::White,
            };
            (field.value.clone(), Style::default().fg(color))
        }
        _ => (field.value.clone(), Style::default().fg(Color::White)),
    }
}

fn render_footer(f: &mut Frame, app: &App, area: Rect) {
    let help = app.fields[app.selected].help;

    let keybindings = if app.mode == Mode::Editing {
        "Enter 确认  Esc 取消"
    } else {
        "↑↓ 选择  Enter 编辑  ^S 保存  q 退出"
    };

    let mut status_spans: Vec<Span> = vec![Span::styled(
        keybindings,
        Style::default().fg(Color::DarkGray),
    )];

    if let Some((msg, _, is_err)) = &app.message {
        let color = if *is_err { Color::Red } else { Color::Green };
        status_spans.push(Span::raw("    "));
        status_spans.push(Span::styled(msg.clone(), Style::default().fg(color)));
    }

    let footer_text = vec![
        Line::raw(""),
        Line::from(Span::styled(
            format!(" {}", help),
            Style::default().fg(Color::DarkGray),
        )),
        Line::from(
            status_spans
                .into_iter()
                .map(|mut s| {
                    // add left padding to first span
                    if s.content.as_ref() == keybindings {
                        s.content = format!(" {}", s.content).into();
                    }
                    s
                })
                .collect::<Vec<_>>(),
        ),
    ];

    let footer = Paragraph::new(footer_text).block(
        Block::default()
            .borders(Borders::TOP)
            .border_style(Style::default().fg(Color::DarkGray)),
    );

    f.render_widget(footer, area);
}

// ── Entry point ──────────────────────────────────────────────────────────────

pub fn run(config_path: PathBuf) -> anyhow::Result<()> {
    // Setup terminal
    terminal::enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new(config_path.clone());
    app.load_from_file();

    let result = event_loop(&mut terminal, &mut app);

    // Restore terminal
    terminal::disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    result?;

    // Post-TUI message
    if app.saved_once {
        eprintln!();
        eprintln!("  配置已保存到 {}", config_path.display());
        eprintln!();
        eprintln!("  启动方式:");
        eprintln!("    aether-proxy              (自动读取 {})", config_path.display());
        eprintln!();
    }

    Ok(())
}

fn event_loop(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> anyhow::Result<()> {
    loop {
        terminal.draw(|f| ui(f, app))?;

        if event::poll(Duration::from_millis(200))? {
            if let Event::Key(key) = event::read()? {
                // Only handle Press events (ignore Release on Windows)
                if key.kind == KeyEventKind::Press && app.handle_key(key) {
                    break;
                }
            }
        }
    }
    Ok(())
}
