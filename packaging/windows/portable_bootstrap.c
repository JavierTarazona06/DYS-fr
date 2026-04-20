#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
#include <commctrl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#if defined(__has_include)
#if __has_include("portable_bootstrap_config.h")
#include "portable_bootstrap_config.h"
#endif
#endif

#ifndef DYS_FR_MANIFEST_URL
#define DYS_FR_MANIFEST_URL L"https://github.com/JavierTarazona06/DYS-fr/releases/download/v0.1.0/DYS-fr-components-0.1.0-hybrid.json"
#endif

#ifndef DYS_FR_APP_VERSION
#define DYS_FR_APP_VERSION "0.1.0"
#endif

#ifndef DYS_FR_FLAVOR
#define DYS_FR_FLAVOR "hybrid"
#endif

#define MANIFEST_NAME L"DYS-fr-runtime-manifest.json"
#define LOCK_NAME L"DYS-fr-portable.lock"
#define BUFFER_SIZE 1048576
#define PATH_BUFFER 4096
#define FIELD_BUFFER 1024
#define URL_BUFFER 8192
#define MAX_COMPONENTS 8
#define MAX_VALIDATION_FILES 64

#ifndef BCRYPT_SUCCESS
#define BCRYPT_SUCCESS(Status) (((NTSTATUS)(Status)) >= 0)
#endif

typedef struct ValidationFile {
    wchar_t path[FIELD_BUFFER];
    uint64_t size;
} ValidationFile;

typedef struct RuntimeComponent {
    char id[64];
    char kind[16];
    char display_name[128];
    wchar_t url[URL_BUFFER];
    wchar_t target[FIELD_BUFFER];
    uint64_t size;
    char sha256[65];
    ValidationFile validation_files[MAX_VALIDATION_FILES];
    size_t validation_count;
} RuntimeComponent;

typedef struct RuntimeManifest {
    char version[128];
    char flavor[64];
    char runtime_exe[256];
    RuntimeComponent components[MAX_COMPONENTS];
    size_t component_count;
    char *raw_json;
    size_t raw_json_size;
} RuntimeManifest;

typedef struct ProgressUi {
    HWND window;
    HWND label;
    HWND bar;
    bool active;
} ProgressUi;

static LRESULT CALLBACK progress_wnd_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam) {
    (void)wparam;
    (void)lparam;
    if (msg == WM_CLOSE) {
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

static void pump_messages(void) {
    MSG msg;
    while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}

static void progress_open(ProgressUi *ui, const wchar_t *message) {
    memset(ui, 0, sizeof(*ui));
    INITCOMMONCONTROLSEX controls;
    controls.dwSize = sizeof(controls);
    controls.dwICC = ICC_PROGRESS_CLASS;
    InitCommonControlsEx(&controls);

    WNDCLASSW wc;
    ZeroMemory(&wc, sizeof(wc));
    wc.lpfnWndProc = progress_wnd_proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = L"DysFrDownloadProgress";
    RegisterClassW(&wc);

    ui->window = CreateWindowExW(
        WS_EX_DLGMODALFRAME,
        wc.lpszClassName,
        L"DYS-fr",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        500,
        150,
        NULL,
        NULL,
        wc.hInstance,
        NULL
    );
    if (!ui->window) {
        return;
    }

    ui->label = CreateWindowExW(0, L"STATIC", message, WS_CHILD | WS_VISIBLE, 20, 20, 450, 28, ui->window, NULL, wc.hInstance, NULL);
    ui->bar = CreateWindowExW(0, PROGRESS_CLASSW, NULL, WS_CHILD | WS_VISIBLE, 20, 62, 450, 24, ui->window, NULL, wc.hInstance, NULL);
    SendMessageW(ui->bar, PBM_SETRANGE, 0, MAKELPARAM(0, 100));
    SendMessageW(ui->bar, PBM_SETPOS, 0, 0);
    ShowWindow(ui->window, SW_SHOW);
    UpdateWindow(ui->window);
    ui->active = true;
    pump_messages();
}

static void progress_update(ProgressUi *ui, const wchar_t *message, uint64_t done, uint64_t total) {
    if (!ui->active) {
        return;
    }
    if (message && ui->label) {
        SetWindowTextW(ui->label, message);
    }
    if (ui->bar && total > 0) {
        int percent = (int)((done * 100ULL) / total);
        if (percent > 100) {
            percent = 100;
        }
        SendMessageW(ui->bar, PBM_SETPOS, percent, 0);
    }
    pump_messages();
}

static void progress_close(ProgressUi *ui) {
    if (ui->window) {
        DestroyWindow(ui->window);
    }
    memset(ui, 0, sizeof(*ui));
}

static void show_error(const wchar_t *message) {
    MessageBoxW(NULL, message, L"DYS-fr", MB_OK | MB_ICONERROR);
}

static void free_manifest(RuntimeManifest *manifest) {
    if (!manifest) {
        return;
    }
    free(manifest->raw_json);
    manifest->raw_json = NULL;
    manifest->raw_json_size = 0;
}

static bool utf8_to_wide(const char *input, wchar_t *output, int output_len) {
    return MultiByteToWideChar(CP_UTF8, 0, input, -1, output, output_len) > 0;
}

static void normalize_relpath(wchar_t *path) {
    for (wchar_t *cursor = path; *cursor; cursor++) {
        if (*cursor == L'/') {
            *cursor = L'\\';
        }
    }
}

static bool utf8_to_wide_path(const char *input, wchar_t *output, int output_len) {
    if (!utf8_to_wide(input, output, output_len)) {
        return false;
    }
    normalize_relpath(output);
    return true;
}

static bool path_join(wchar_t *out, size_t out_len, const wchar_t *left, const wchar_t *right) {
    size_t left_len = wcslen(left);
    const wchar_t *sep = (left_len > 0 && (left[left_len - 1] == L'\\' || left[left_len - 1] == L'/')) ? L"" : L"\\";
    return swprintf(out, out_len, L"%ls%ls%ls", left, sep, right) > 0;
}

static bool get_parent_dir(const wchar_t *path, wchar_t *parent, size_t parent_len) {
    wcsncpy(parent, path, parent_len - 1);
    parent[parent_len - 1] = L'\0';
    wchar_t *slash = wcsrchr(parent, L'\\');
    wchar_t *slash_alt = wcsrchr(parent, L'/');
    if (slash_alt && (!slash || slash_alt > slash)) {
        slash = slash_alt;
    }
    if (!slash) {
        return false;
    }
    *slash = L'\0';
    return true;
}

static bool ensure_dir_recursive(const wchar_t *path) {
    wchar_t temp[PATH_BUFFER];
    wcsncpy(temp, path, PATH_BUFFER - 1);
    temp[PATH_BUFFER - 1] = L'\0';

    size_t len = wcslen(temp);
    if (len == 0) {
        return false;
    }

    wchar_t *cursor = temp;
    if (len >= 3 && temp[1] == L':' && (temp[2] == L'\\' || temp[2] == L'/')) {
        cursor = temp + 3;
    }

    for (; *cursor; cursor++) {
        if (*cursor == L'\\' || *cursor == L'/') {
            wchar_t saved = *cursor;
            *cursor = L'\0';
            if (wcslen(temp) > 0 && !CreateDirectoryW(temp, NULL)) {
                DWORD err = GetLastError();
                if (err != ERROR_ALREADY_EXISTS) {
                    *cursor = saved;
                    return false;
                }
            }
            *cursor = saved;
        }
    }

    if (!CreateDirectoryW(temp, NULL)) {
        DWORD err = GetLastError();
        if (err != ERROR_ALREADY_EXISTS) {
            return false;
        }
    }
    return true;
}

static bool ensure_parent_dir(const wchar_t *path) {
    wchar_t parent[PATH_BUFFER];
    return get_parent_dir(path, parent, PATH_BUFFER) && ensure_dir_recursive(parent);
}

static bool directory_writable(const wchar_t *dir) {
    wchar_t temp_path[PATH_BUFFER];
    DWORD pid = GetCurrentProcessId();
    if (swprintf(temp_path, PATH_BUFFER, L"%ls\\.dys-fr-write-test-%lu.tmp", dir, pid) <= 0) {
        return false;
    }
    HANDLE handle = CreateFileW(temp_path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_TEMPORARY, NULL);
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    CloseHandle(handle);
    DeleteFileW(temp_path);
    return true;
}

static bool read_file_bytes(const wchar_t *path, char **buffer, size_t *size) {
    *buffer = NULL;
    *size = 0;
    HANDLE handle = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    LARGE_INTEGER file_size;
    if (!GetFileSizeEx(handle, &file_size) || file_size.QuadPart < 0) {
        CloseHandle(handle);
        return false;
    }
    char *data = (char *)malloc((size_t)file_size.QuadPart + 1);
    if (!data) {
        CloseHandle(handle);
        return false;
    }
    DWORD bytes_read = 0;
    bool ok = true;
    if (file_size.QuadPart > 0) {
        ok = ReadFile(handle, data, (DWORD)file_size.QuadPart, &bytes_read, NULL) && bytes_read == (DWORD)file_size.QuadPart;
    }
    CloseHandle(handle);
    if (!ok) {
        free(data);
        return false;
    }
    data[file_size.QuadPart] = '\0';
    *buffer = data;
    *size = (size_t)file_size.QuadPart;
    return true;
}

static bool write_file_bytes(const wchar_t *path, const char *buffer, size_t size) {
    if (!ensure_parent_dir(path)) {
        return false;
    }
    HANDLE handle = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    DWORD written = 0;
    bool ok = WriteFile(handle, buffer, (DWORD)size, &written, NULL) && written == (DWORD)size;
    CloseHandle(handle);
    return ok;
}

static bool file_has_size(const wchar_t *path, uint64_t expected_size) {
    HANDLE handle = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    LARGE_INTEGER size;
    bool ok = GetFileSizeEx(handle, &size) && (uint64_t)size.QuadPart == expected_size;
    CloseHandle(handle);
    return ok;
}

static const char *skip_ws(const char *cursor, const char *end) {
    while (cursor < end && (*cursor == ' ' || *cursor == '\n' || *cursor == '\r' || *cursor == '\t')) {
        cursor++;
    }
    return cursor;
}

static const char *bounded_strstr(const char *start, const char *end, const char *needle) {
    size_t needle_len = strlen(needle);
    for (const char *cursor = start; cursor + needle_len <= end; cursor++) {
        if (memcmp(cursor, needle, needle_len) == 0) {
            return cursor;
        }
    }
    return NULL;
}

static const char *find_json_value_between(const char *start, const char *end, const char *key) {
    char pattern[256];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *key_pos = bounded_strstr(start, end, pattern);
    if (!key_pos) {
        return NULL;
    }
    const char *colon = memchr(key_pos + strlen(pattern), ':', (size_t)(end - (key_pos + strlen(pattern))));
    if (!colon) {
        return NULL;
    }
    return skip_ws(colon + 1, end);
}

static bool json_get_string_between(const char *start, const char *end, const char *key, char *out, size_t out_len) {
    const char *value = find_json_value_between(start, end, key);
    if (!value || value >= end || *value != '"' || out_len == 0) {
        return false;
    }
    value++;
    size_t index = 0;
    while (value < end && *value && *value != '"') {
        if (*value == '\\' && value + 1 < end) {
            value++;
        }
        if (index + 1 < out_len) {
            out[index++] = *value;
        }
        value++;
    }
    out[index] = '\0';
    return value < end && *value == '"';
}

static bool json_get_uint64_between(const char *start, const char *end, const char *key, uint64_t *out) {
    const char *value = find_json_value_between(start, end, key);
    if (!value || value >= end) {
        return false;
    }
    *out = _strtoui64(value, NULL, 10);
    return true;
}

static bool find_json_array(const char *start, const char *end, const char *key, const char **array_start, const char **array_end) {
    const char *value = find_json_value_between(start, end, key);
    if (!value || value >= end || *value != '[') {
        return false;
    }
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (const char *cursor = value; cursor < end; cursor++) {
        char ch = *cursor;
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
        } else if (ch == '[') {
            depth++;
        } else if (ch == ']') {
            depth--;
            if (depth == 0) {
                *array_start = value + 1;
                *array_end = cursor;
                return true;
            }
        }
    }
    return false;
}

static bool next_json_object(const char **cursor_ref, const char *end, const char **object_start, const char **object_end) {
    const char *cursor = *cursor_ref;
    while (cursor < end && *cursor != '{') {
        cursor++;
    }
    if (cursor >= end) {
        return false;
    }
    const char *start = cursor;
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (; cursor < end; cursor++) {
        char ch = *cursor;
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
        } else if (ch == '{') {
            depth++;
        } else if (ch == '}') {
            depth--;
            if (depth == 0) {
                *object_start = start;
                *object_end = cursor + 1;
                *cursor_ref = cursor + 1;
                return true;
            }
        }
    }
    return false;
}

static bool parse_validation_files(const char *start, const char *end, RuntimeComponent *component) {
    const char *array_start = NULL;
    const char *array_end = NULL;
    if (!find_json_array(start, end, "validation_files", &array_start, &array_end)) {
        return false;
    }

    const char *cursor = array_start;
    const char *object_start = NULL;
    const char *object_end = NULL;
    component->validation_count = 0;
    while (next_json_object(&cursor, array_end, &object_start, &object_end)) {
        if (component->validation_count >= MAX_VALIDATION_FILES) {
            return false;
        }
        char path_utf8[FIELD_BUFFER];
        uint64_t size = 0;
        if (!json_get_string_between(object_start, object_end, "path", path_utf8, sizeof(path_utf8)) ||
            !json_get_uint64_between(object_start, object_end, "size", &size)) {
            return false;
        }
        ValidationFile *file = &component->validation_files[component->validation_count++];
        if (!utf8_to_wide_path(path_utf8, file->path, FIELD_BUFFER)) {
            return false;
        }
        file->size = size;
    }
    return component->validation_count > 0;
}

static bool parse_components(const char *start, const char *end, RuntimeManifest *manifest) {
    const char *array_start = NULL;
    const char *array_end = NULL;
    if (!find_json_array(start, end, "components", &array_start, &array_end)) {
        return false;
    }

    const char *cursor = array_start;
    const char *object_start = NULL;
    const char *object_end = NULL;
    manifest->component_count = 0;
    while (next_json_object(&cursor, array_end, &object_start, &object_end)) {
        if (manifest->component_count >= MAX_COMPONENTS) {
            return false;
        }
        RuntimeComponent *component = &manifest->components[manifest->component_count++];
        char url_utf8[URL_BUFFER];
        char target_utf8[FIELD_BUFFER];
        if (!json_get_string_between(object_start, object_end, "id", component->id, sizeof(component->id)) ||
            !json_get_string_between(object_start, object_end, "kind", component->kind, sizeof(component->kind)) ||
            !json_get_string_between(object_start, object_end, "display_name", component->display_name, sizeof(component->display_name)) ||
            !json_get_string_between(object_start, object_end, "url", url_utf8, sizeof(url_utf8)) ||
            !json_get_string_between(object_start, object_end, "target", target_utf8, sizeof(target_utf8)) ||
            !json_get_uint64_between(object_start, object_end, "size", &component->size) ||
            !json_get_string_between(object_start, object_end, "sha256", component->sha256, sizeof(component->sha256)) ||
            !utf8_to_wide(url_utf8, component->url, URL_BUFFER) ||
            !utf8_to_wide_path(target_utf8, component->target, FIELD_BUFFER) ||
            !parse_validation_files(object_start, object_end, component)) {
            return false;
        }
    }
    return manifest->component_count > 0;
}

static bool parse_manifest_json(char *json, size_t json_size, RuntimeManifest *manifest) {
    memset(manifest, 0, sizeof(*manifest));
    manifest->raw_json = json;
    manifest->raw_json_size = json_size;
    const char *start = json;
    const char *end = json + json_size;
    return json_get_string_between(start, end, "version", manifest->version, sizeof(manifest->version)) &&
           json_get_string_between(start, end, "flavor", manifest->flavor, sizeof(manifest->flavor)) &&
           json_get_string_between(start, end, "runtime_exe", manifest->runtime_exe, sizeof(manifest->runtime_exe)) &&
           parse_components(start, end, manifest);
}

static bool manifest_matches_build(const RuntimeManifest *manifest) {
    return strcmp(manifest->version, DYS_FR_APP_VERSION) == 0 && strcmp(manifest->flavor, DYS_FR_FLAVOR) == 0;
}

static bool validate_component_files(const wchar_t *target_dir, const RuntimeComponent *component) {
    for (size_t i = 0; i < component->validation_count; i++) {
        wchar_t path[PATH_BUFFER];
        if (!path_join(path, PATH_BUFFER, target_dir, component->validation_files[i].path) ||
            !file_has_size(path, component->validation_files[i].size)) {
            return false;
        }
    }
    return true;
}

static bool validate_runtime_files(const wchar_t *target_dir, const RuntimeManifest *manifest) {
    if (!manifest_matches_build(manifest)) {
        return false;
    }
    for (size_t i = 0; i < manifest->component_count; i++) {
        if (!validate_component_files(target_dir, &manifest->components[i])) {
            return false;
        }
    }
    return true;
}

static bool read_manifest_file(const wchar_t *path, RuntimeManifest *manifest) {
    char *json = NULL;
    size_t json_size = 0;
    if (!read_file_bytes(path, &json, &json_size)) {
        return false;
    }
    if (!parse_manifest_json(json, json_size, manifest)) {
        free(json);
        return false;
    }
    return true;
}

static bool read_local_manifest(const wchar_t *target_dir, RuntimeManifest *manifest) {
    wchar_t manifest_path[PATH_BUFFER];
    return path_join(manifest_path, PATH_BUFFER, target_dir, MANIFEST_NAME) &&
           read_manifest_file(manifest_path, manifest);
}

static bool remove_tree(const wchar_t *path) {
    DWORD attrs = GetFileAttributesW(path);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        return true;
    }
    if (!(attrs & FILE_ATTRIBUTE_DIRECTORY)) {
        SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL);
        return DeleteFileW(path) || GetLastError() == ERROR_FILE_NOT_FOUND;
    }

    wchar_t pattern[PATH_BUFFER];
    if (swprintf(pattern, PATH_BUFFER, L"%ls\\*", path) <= 0) {
        return false;
    }

    WIN32_FIND_DATAW data;
    HANDLE find = FindFirstFileW(pattern, &data);
    if (find != INVALID_HANDLE_VALUE) {
        do {
            if (wcscmp(data.cFileName, L".") == 0 || wcscmp(data.cFileName, L"..") == 0) {
                continue;
            }
            wchar_t child[PATH_BUFFER];
            if (!path_join(child, PATH_BUFFER, path, data.cFileName) || !remove_tree(child)) {
                FindClose(find);
                return false;
            }
        } while (FindNextFileW(find, &data));
        FindClose(find);
    }

    SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL);
    return RemoveDirectoryW(path) || GetLastError() == ERROR_FILE_NOT_FOUND;
}

static bool copy_tree_merge(const wchar_t *source, const wchar_t *destination) {
    DWORD attrs = GetFileAttributesW(source);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        return false;
    }
    if (!(attrs & FILE_ATTRIBUTE_DIRECTORY)) {
        return ensure_parent_dir(destination) && CopyFileW(source, destination, FALSE);
    }
    if (!ensure_dir_recursive(destination)) {
        return false;
    }

    wchar_t pattern[PATH_BUFFER];
    if (swprintf(pattern, PATH_BUFFER, L"%ls\\*", source) <= 0) {
        return false;
    }
    WIN32_FIND_DATAW data;
    HANDLE find = FindFirstFileW(pattern, &data);
    if (find == INVALID_HANDLE_VALUE) {
        return true;
    }
    do {
        if (wcscmp(data.cFileName, L".") == 0 || wcscmp(data.cFileName, L"..") == 0) {
            continue;
        }
        wchar_t child_source[PATH_BUFFER];
        wchar_t child_destination[PATH_BUFFER];
        if (!path_join(child_source, PATH_BUFFER, source, data.cFileName) ||
            !path_join(child_destination, PATH_BUFFER, destination, data.cFileName) ||
            !copy_tree_merge(child_source, child_destination)) {
            FindClose(find);
            return false;
        }
    } while (FindNextFileW(find, &data));
    FindClose(find);
    return true;
}

static bool build_http_request(const wchar_t *url, HINTERNET *session, HINTERNET *connect, HINTERNET *request) {
    URL_COMPONENTSW parts;
    ZeroMemory(&parts, sizeof(parts));
    parts.dwStructSize = sizeof(parts);
    parts.dwSchemeLength = (DWORD)-1;
    parts.dwHostNameLength = (DWORD)-1;
    parts.dwUrlPathLength = (DWORD)-1;
    parts.dwExtraInfoLength = (DWORD)-1;

    if (!WinHttpCrackUrl(url, 0, 0, &parts)) {
        return false;
    }

    wchar_t host[512];
    wchar_t path[URL_BUFFER];
    wcsncpy(host, parts.lpszHostName, parts.dwHostNameLength);
    host[parts.dwHostNameLength] = L'\0';
    wcsncpy(path, parts.lpszUrlPath, parts.dwUrlPathLength);
    path[parts.dwUrlPathLength] = L'\0';
    if (parts.dwExtraInfoLength > 0) {
        wcsncat(path, parts.lpszExtraInfo, parts.dwExtraInfoLength);
    }

    *session = WinHttpOpen(L"DYS-fr Launcher/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!*session) {
        return false;
    }
    *connect = WinHttpConnect(*session, host, parts.nPort, 0);
    if (!*connect) {
        WinHttpCloseHandle(*session);
        return false;
    }

    DWORD flags = parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
    *request = WinHttpOpenRequest(*connect, L"GET", path, NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags);
    if (!*request) {
        WinHttpCloseHandle(*connect);
        WinHttpCloseHandle(*session);
        return false;
    }

    DWORD redirect_policy = WINHTTP_OPTION_REDIRECT_POLICY_ALWAYS;
    WinHttpSetOption(*request, WINHTTP_OPTION_REDIRECT_POLICY, &redirect_policy, sizeof(redirect_policy));
    return true;
}

static bool query_status_ok(HINTERNET request) {
    DWORD status_code = 0;
    DWORD status_size = sizeof(status_code);
    if (!WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, NULL, &status_code, &status_size, NULL)) {
        return false;
    }
    return status_code >= 200 && status_code < 300;
}

static uint64_t query_content_length(HINTERNET request) {
    wchar_t length_text[64];
    DWORD length_size = sizeof(length_text);
    if (!WinHttpQueryHeaders(request, WINHTTP_QUERY_CONTENT_LENGTH, NULL, length_text, &length_size, NULL)) {
        return 0;
    }
    return _wcstoui64(length_text, NULL, 10);
}

static bool open_http_response(const wchar_t *url, HINTERNET *session, HINTERNET *connect, HINTERNET *request) {
    if (!build_http_request(url, session, connect, request)) {
        return false;
    }
    if (!WinHttpSendRequest(*request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) ||
        !WinHttpReceiveResponse(*request, NULL) || !query_status_ok(*request)) {
        WinHttpCloseHandle(*request);
        WinHttpCloseHandle(*connect);
        WinHttpCloseHandle(*session);
        return false;
    }
    return true;
}

static bool download_to_memory(const wchar_t *url, char **out, size_t *out_size, size_t max_size) {
    *out = NULL;
    *out_size = 0;
    HINTERNET session = NULL, connect = NULL, request = NULL;
    if (!open_http_response(url, &session, &connect, &request)) {
        return false;
    }

    size_t capacity = 8192;
    char *buffer = (char *)malloc(capacity + 1);
    if (!buffer) {
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connect);
        WinHttpCloseHandle(session);
        return false;
    }

    bool ok = true;
    while (ok) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(request, &available)) {
            ok = false;
            break;
        }
        if (available == 0) {
            break;
        }
        if (*out_size + available > max_size) {
            ok = false;
            break;
        }
        if (*out_size + available + 1 > capacity) {
            while (*out_size + available + 1 > capacity) {
                capacity *= 2;
            }
            char *new_buffer = (char *)realloc(buffer, capacity + 1);
            if (!new_buffer) {
                ok = false;
                break;
            }
            buffer = new_buffer;
        }
        DWORD read = 0;
        if (!WinHttpReadData(request, buffer + *out_size, available, &read)) {
            ok = false;
            break;
        }
        *out_size += read;
    }

    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);

    if (!ok) {
        free(buffer);
        *out_size = 0;
        return false;
    }
    buffer[*out_size] = '\0';
    *out = buffer;
    return true;
}

static bool download_to_file(const wchar_t *url, const wchar_t *path, uint64_t expected_size, const wchar_t *display_name) {
    HINTERNET session = NULL, connect = NULL, request = NULL;
    if (!open_http_response(url, &session, &connect, &request)) {
        return false;
    }

    if (!ensure_parent_dir(path)) {
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connect);
        WinHttpCloseHandle(session);
        return false;
    }
    HANDLE output = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (output == INVALID_HANDLE_VALUE) {
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connect);
        WinHttpCloseHandle(session);
        return false;
    }

    ProgressUi ui;
    wchar_t title[256];
    swprintf(title, 256, L"Downloading %ls...", display_name);
    progress_open(&ui, title);
    uint64_t total = expected_size ? expected_size : query_content_length(request);
    uint64_t downloaded = 0;
    unsigned char *buffer = (unsigned char *)malloc(BUFFER_SIZE);
    bool ok = buffer != NULL;

    while (ok) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(request, &available)) {
            ok = false;
            break;
        }
        if (available == 0) {
            break;
        }
        while (available > 0) {
            DWORD chunk = available > BUFFER_SIZE ? BUFFER_SIZE : available;
            DWORD read = 0;
            DWORD written = 0;
            if (!WinHttpReadData(request, buffer, chunk, &read) || read == 0 ||
                !WriteFile(output, buffer, read, &written, NULL) || written != read) {
                ok = false;
                break;
            }
            downloaded += read;
            available -= read;
            wchar_t label[256];
            if (total > 0) {
                swprintf(label, 256, L"Downloading %ls... %llu / %llu MB", display_name, downloaded / 1048576ULL, total / 1048576ULL);
            } else {
                swprintf(label, 256, L"Downloading %ls... %llu MB", display_name, downloaded / 1048576ULL);
            }
            progress_update(&ui, label, downloaded, total);
        }
    }

    free(buffer);
    CloseHandle(output);
    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);
    progress_close(&ui);

    if (!ok || (expected_size > 0 && downloaded != expected_size)) {
        DeleteFileW(path);
        return false;
    }
    return true;
}

static bool sha256_file(const wchar_t *path, char out_hex[65]) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    DWORD object_length = 0, hash_length = 0, data_length = 0;
    unsigned char *hash_object = NULL;
    unsigned char hash_bytes[32];
    bool ok = false;

    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0)) ||
        !BCRYPT_SUCCESS(BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_length, sizeof(object_length), &data_length, 0)) ||
        !BCRYPT_SUCCESS(BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH, (PUCHAR)&hash_length, sizeof(hash_length), &data_length, 0)) ||
        hash_length != sizeof(hash_bytes)) {
        goto cleanup;
    }

    hash_object = (unsigned char *)malloc(object_length);
    if (!hash_object || !BCRYPT_SUCCESS(BCryptCreateHash(algorithm, &hash, hash_object, object_length, NULL, 0, 0))) {
        goto cleanup;
    }

    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        goto cleanup;
    }

    unsigned char *buffer = (unsigned char *)malloc(BUFFER_SIZE);
    if (!buffer) {
        CloseHandle(file);
        goto cleanup;
    }

    while (true) {
        DWORD read = 0;
        if (!ReadFile(file, buffer, BUFFER_SIZE, &read, NULL)) {
            break;
        }
        if (read == 0) {
            ok = true;
            break;
        }
        if (!BCRYPT_SUCCESS(BCryptHashData(hash, buffer, read, 0))) {
            break;
        }
    }

    free(buffer);
    CloseHandle(file);
    if (!ok || !BCRYPT_SUCCESS(BCryptFinishHash(hash, hash_bytes, sizeof(hash_bytes), 0))) {
        ok = false;
        goto cleanup;
    }

    for (size_t i = 0; i < sizeof(hash_bytes); i++) {
        sprintf(out_hex + (i * 2), "%02x", hash_bytes[i]);
    }
    out_hex[64] = '\0';

cleanup:
    if (hash) {
        BCryptDestroyHash(hash);
    }
    if (algorithm) {
        BCryptCloseAlgorithmProvider(algorithm, 0);
    }
    free(hash_object);
    return ok;
}

static bool run_process_and_wait(wchar_t *command_line, const wchar_t *cwd) {
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);

    if (!CreateProcessW(NULL, command_line, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, cwd, &startup, &process)) {
        return false;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return exit_code == 0;
}

static bool powershell_quote(const wchar_t *input, wchar_t *output, size_t output_len) {
    size_t index = 0;
    if (output_len < 3) {
        return false;
    }
    output[index++] = L'\'';
    for (const wchar_t *cursor = input; *cursor; cursor++) {
        if (index + 3 >= output_len) {
            return false;
        }
        output[index++] = *cursor;
        if (*cursor == L'\'') {
            output[index++] = L'\'';
        }
    }
    output[index++] = L'\'';
    output[index] = L'\0';
    return true;
}

static bool extract_zip(const wchar_t *zip_path, const wchar_t *staging_dir) {
    wchar_t quoted_zip[PATH_BUFFER * 2];
    wchar_t quoted_staging[PATH_BUFFER * 2];
    wchar_t command_line[PATH_BUFFER * 5];
    if (!powershell_quote(zip_path, quoted_zip, PATH_BUFFER * 2) ||
        !powershell_quote(staging_dir, quoted_staging, PATH_BUFFER * 2) ||
        swprintf(
            command_line,
            PATH_BUFFER * 5,
            L"powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \"$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath %ls -DestinationPath %ls -Force\"",
            quoted_zip,
            quoted_staging
        ) <= 0) {
        return false;
    }
    return run_process_and_wait(command_line, staging_dir);
}

static bool write_manifest_file(const wchar_t *target_dir, const RuntimeManifest *manifest) {
    wchar_t manifest_path[PATH_BUFFER];
    return path_join(manifest_path, PATH_BUFFER, target_dir, MANIFEST_NAME) &&
           write_file_bytes(manifest_path, manifest->raw_json, manifest->raw_json_size);
}

static bool filename_from_url(const wchar_t *url, wchar_t *out, size_t out_len) {
    const wchar_t *name = wcsrchr(url, L'/');
    name = name ? name + 1 : url;
    if (!*name) {
        return false;
    }
    const wchar_t *query = wcschr(name, L'?');
    size_t len = query ? (size_t)(query - name) : wcslen(name);
    if (len == 0 || len >= out_len) {
        return false;
    }
    wcsncpy(out, name, len);
    out[len] = L'\0';
    return true;
}

static bool find_adjacent_component_file(const wchar_t *target_dir, const RuntimeComponent *component, wchar_t *path, size_t path_len) {
    wchar_t filename[PATH_BUFFER];
    return filename_from_url(component->url, filename, PATH_BUFFER) &&
           path_join(path, path_len, target_dir, filename) &&
           file_has_size(path, component->size);
}

static bool verify_component_payload(const RuntimeComponent *component, const wchar_t *path) {
    char actual_sha[65];
    return file_has_size(path, component->size) &&
           sha256_file(path, actual_sha) &&
           _stricmp(actual_sha, component->sha256) == 0;
}

static bool obtain_component_payload(const wchar_t *target_dir, const RuntimeComponent *component, wchar_t *payload_path, size_t payload_path_len, bool *delete_after) {
    *delete_after = false;
    if (find_adjacent_component_file(target_dir, component, payload_path, payload_path_len)) {
        return verify_component_payload(component, payload_path);
    }

    wchar_t display_name[128];
    if (!utf8_to_wide(component->display_name, display_name, 128)) {
        wcscpy(display_name, L"component");
    }
    DWORD pid = GetCurrentProcessId();
    wchar_t extension[16] = L".bin";
    if (_stricmp(component->kind, "zip") == 0) {
        wcscpy(extension, L".zip");
    }
    if (swprintf(payload_path, payload_path_len, L"%ls\\.dys-fr-download-%lu-%S%ls", target_dir, pid, component->id, extension) <= 0) {
        return false;
    }
    DeleteFileW(payload_path);
    if (!download_to_file(component->url, payload_path, component->size, display_name)) {
        return false;
    }
    *delete_after = true;
    return verify_component_payload(component, payload_path);
}

static bool install_zip_component(const wchar_t *target_dir, const RuntimeComponent *component, const wchar_t *zip_path) {
    DWORD pid = GetCurrentProcessId();
    wchar_t staging_dir[PATH_BUFFER];
    if (swprintf(staging_dir, PATH_BUFFER, L"%ls\\.dys-fr-staging-%lu-%S", target_dir, pid, component->id) <= 0) {
        return false;
    }
    remove_tree(staging_dir);
    if (!ensure_dir_recursive(staging_dir)) {
        return false;
    }
    if (!extract_zip(zip_path, staging_dir)) {
        remove_tree(staging_dir);
        return false;
    }
    if (!validate_component_files(staging_dir, component)) {
        remove_tree(staging_dir);
        return false;
    }
    if (!copy_tree_merge(staging_dir, target_dir)) {
        remove_tree(staging_dir);
        return false;
    }
    remove_tree(staging_dir);
    return validate_component_files(target_dir, component);
}

static bool install_file_component(const wchar_t *target_dir, const RuntimeComponent *component, const wchar_t *source_path) {
    wchar_t destination[PATH_BUFFER];
    if (!path_join(destination, PATH_BUFFER, target_dir, component->target) || !ensure_parent_dir(destination)) {
        return false;
    }
    if (!CopyFileW(source_path, destination, FALSE)) {
        return false;
    }
    return validate_component_files(target_dir, component);
}

static bool install_component(const wchar_t *target_dir, const RuntimeComponent *component) {
    if (validate_component_files(target_dir, component)) {
        return true;
    }

    wchar_t payload_path[PATH_BUFFER];
    bool delete_after = false;
    if (!obtain_component_payload(target_dir, component, payload_path, PATH_BUFFER, &delete_after)) {
        if (delete_after) {
            DeleteFileW(payload_path);
        }
        return false;
    }

    bool ok = false;
    if (_stricmp(component->kind, "zip") == 0) {
        ok = install_zip_component(target_dir, component, payload_path);
    } else if (_stricmp(component->kind, "file") == 0) {
        ok = install_file_component(target_dir, component, payload_path);
    }

    if (delete_after) {
        DeleteFileW(payload_path);
    }
    return ok;
}

static bool install_runtime(const wchar_t *target_dir, const RuntimeManifest *manifest) {
    for (size_t i = 0; i < manifest->component_count; i++) {
        if (!install_component(target_dir, &manifest->components[i])) {
            return false;
        }
    }
    return validate_runtime_files(target_dir, manifest) && write_manifest_file(target_dir, manifest);
}

static bool read_adjacent_release_manifest(const wchar_t *target_dir, RuntimeManifest *manifest) {
    char filename_utf8[512];
    int written = snprintf(filename_utf8, sizeof(filename_utf8), "DYS-fr-components-%s-%s.json", DYS_FR_APP_VERSION, DYS_FR_FLAVOR);
    if (written <= 0 || (size_t)written >= sizeof(filename_utf8)) {
        return false;
    }

    wchar_t filename[PATH_BUFFER];
    wchar_t manifest_path[PATH_BUFFER];
    if (!utf8_to_wide_path(filename_utf8, filename, PATH_BUFFER) || !path_join(manifest_path, PATH_BUFFER, target_dir, filename)) {
        return false;
    }
    if (!read_manifest_file(manifest_path, manifest)) {
        return false;
    }
    if (!manifest_matches_build(manifest)) {
        free_manifest(manifest);
        return false;
    }
    return true;
}

static HANDLE acquire_lock(const wchar_t *target_dir) {
    wchar_t lock_path[PATH_BUFFER];
    if (!path_join(lock_path, PATH_BUFFER, target_dir, LOCK_NAME)) {
        return INVALID_HANDLE_VALUE;
    }
    HANDLE lock = CreateFileW(lock_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_HIDDEN, NULL);
    if (lock == INVALID_HANDLE_VALUE) {
        return INVALID_HANDLE_VALUE;
    }

    OVERLAPPED overlapped;
    ZeroMemory(&overlapped, sizeof(overlapped));
    while (!LockFileEx(lock, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &overlapped)) {
        Sleep(200);
        pump_messages();
    }
    return lock;
}

static void release_lock(HANDLE lock) {
    if (lock == INVALID_HANDLE_VALUE) {
        return;
    }
    OVERLAPPED overlapped;
    ZeroMemory(&overlapped, sizeof(overlapped));
    UnlockFileEx(lock, 0, 1, 0, &overlapped);
    CloseHandle(lock);
}

static bool launch_runtime(const wchar_t *target_dir, const RuntimeManifest *manifest) {
    wchar_t runtime_exe_wide[PATH_BUFFER];
    wchar_t runtime_path[PATH_BUFFER];
    wchar_t command_line[PATH_BUFFER + 4];
    if (!utf8_to_wide_path(manifest->runtime_exe, runtime_exe_wide, PATH_BUFFER) ||
        !path_join(runtime_path, PATH_BUFFER, target_dir, runtime_exe_wide) ||
        swprintf(command_line, PATH_BUFFER + 4, L"\"%ls\"", runtime_path) <= 0) {
        return false;
    }

    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);

    if (!CreateProcessW(runtime_path, command_line, NULL, NULL, FALSE, 0, NULL, target_dir, &startup, &process)) {
        return false;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return true;
}

static bool get_manifest_url(wchar_t *url, size_t url_len) {
    DWORD env_len = GetEnvironmentVariableW(L"DYS_FR_RUNTIME_MANIFEST_URL", url, (DWORD)url_len);
    if (env_len > 0 && env_len < url_len) {
        return true;
    }
    wcsncpy(url, DYS_FR_MANIFEST_URL, url_len - 1);
    url[url_len - 1] = L'\0';
    return true;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show_command) {
    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show_command;

    wchar_t exe_path[PATH_BUFFER];
    wchar_t target_dir[PATH_BUFFER];
    if (GetModuleFileNameW(NULL, exe_path, PATH_BUFFER) == 0 || !get_parent_dir(exe_path, target_dir, PATH_BUFFER)) {
        show_error(L"Could not resolve the DYS-fr executable path.");
        return 1;
    }

    RuntimeManifest *local_manifest = calloc(1, sizeof(*local_manifest));
    RuntimeManifest *remote_manifest = calloc(1, sizeof(*remote_manifest));
    if (!local_manifest || !remote_manifest) {
        free(local_manifest);
        free(remote_manifest);
        show_error(L"DYS-fr could not allocate memory for the launcher.");
        return 1;
    }

    if (read_local_manifest(target_dir, local_manifest)) {
        if (validate_runtime_files(target_dir, local_manifest)) {
            bool launched = launch_runtime(target_dir, local_manifest);
            free_manifest(local_manifest);
            if (launched) {
                free(local_manifest);
                free(remote_manifest);
                return 0;
            }
        } else {
            free_manifest(local_manifest);
        }
    }

    if (!directory_writable(target_dir)) {
        free(local_manifest);
        free(remote_manifest);
        show_error(L"DYS-fr needs to create _internal next to DYS-fr.exe. Move DYS-fr.exe to a writable folder and run it again.");
        return 1;
    }

    HANDLE lock = acquire_lock(target_dir);
    if (lock == INVALID_HANDLE_VALUE) {
        free(local_manifest);
        free(remote_manifest);
        show_error(L"Could not acquire the DYS-fr installation lock.");
        return 1;
    }

    if (read_local_manifest(target_dir, local_manifest)) {
        if (validate_runtime_files(target_dir, local_manifest)) {
            release_lock(lock);
            bool launched = launch_runtime(target_dir, local_manifest);
            free_manifest(local_manifest);
            free(local_manifest);
            free(remote_manifest);
            return launched ? 0 : 1;
        }
        free_manifest(local_manifest);
    }

    bool ok = false;
    if (read_adjacent_release_manifest(target_dir, remote_manifest)) {
        ok = install_runtime(target_dir, remote_manifest);
    }

    if (!ok) {
        free_manifest(remote_manifest);
        wchar_t manifest_url[URL_BUFFER];
        char *remote_json = NULL;
        size_t remote_json_size = 0;
        ok = get_manifest_url(manifest_url, URL_BUFFER) &&
             download_to_memory(manifest_url, &remote_json, &remote_json_size, 1024 * 1024) &&
             parse_manifest_json(remote_json, remote_json_size, remote_manifest) &&
             install_runtime(target_dir, remote_manifest);
    }

    release_lock(lock);

    if (!ok) {
        free_manifest(remote_manifest);
        free(local_manifest);
        free(remote_manifest);
        show_error(L"DYS-fr could not download or install all required components. Check your internet connection and that the release files are available.");
        return 1;
    }

    bool launched = launch_runtime(target_dir, remote_manifest);
    free_manifest(remote_manifest);
    free(local_manifest);
    free(remote_manifest);
    if (!launched) {
        show_error(L"Could not launch the DYS-fr runtime.");
        return 1;
    }
    return 0;
}
