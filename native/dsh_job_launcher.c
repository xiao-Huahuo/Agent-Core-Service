/*
 * DSH Windows Job Object launcher.
 *
 * Usage: dsh_job_launcher.exe <runtime.exe> [runtime arguments...]
 * The launcher inherits SDK stdio, creates the Runtime suspended, assigns it
 * to a KILL_ON_JOB_CLOSE Job, resumes it, and returns the Runtime exit code.
 */

#include <windows.h>
#include <wchar.h>
#include <stdlib.h>

static int append_quoted(wchar_t **buffer, size_t *length, size_t *capacity, const wchar_t *arg) {
    size_t extra = wcslen(arg) * 2 + 4;
    if (*length + extra >= *capacity) {
        size_t next = (*capacity + extra) * 2;
        wchar_t *grown = (wchar_t *)realloc(*buffer, next * sizeof(wchar_t));
        if (grown == NULL) return 0;
        *buffer = grown;
        *capacity = next;
    }
    if (*length) (*buffer)[(*length)++] = L' ';
    (*buffer)[(*length)++] = L'"';
    size_t slashes = 0;
    for (const wchar_t *cursor = arg; ; ++cursor) {
        if (*cursor == L'\\') {
            ++slashes;
            continue;
        }
        if (*cursor == L'"' || *cursor == L'\0') {
            size_t count = slashes * 2 + (*cursor == L'"' ? 1 : 0);
            for (size_t index = 0; index < count; ++index) (*buffer)[(*length)++] = L'\\';
        } else {
            for (size_t index = 0; index < slashes; ++index) (*buffer)[(*length)++] = L'\\';
        }
        slashes = 0;
        if (*cursor == L'\0') break;
        (*buffer)[(*length)++] = *cursor;
    }
    (*buffer)[(*length)++] = L'"';
    (*buffer)[*length] = L'\0';
    return 1;
}

int wmain(int argc, wchar_t **argv) {
    if (argc < 2) return 64;
    HANDLE job = CreateJobObjectW(NULL, NULL);
    if (job == NULL) return 65;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    ZeroMemory(&limits, sizeof(limits));
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        CloseHandle(job);
        return 66;
    }

    size_t capacity = 1024, length = 0;
    wchar_t *command = (wchar_t *)calloc(capacity, sizeof(wchar_t));
    if (command == NULL) {
        CloseHandle(job);
        return 67;
    }
    for (int index = 1; index < argc; ++index) {
        if (!append_quoted(&command, &length, &capacity, argv[index])) {
            free(command);
            CloseHandle(job);
            return 67;
        }
    }

    SetHandleInformation(GetStdHandle(STD_INPUT_HANDLE), HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    SetHandleInformation(GetStdHandle(STD_OUTPUT_HANDLE), HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    SetHandleInformation(GetStdHandle(STD_ERROR_HANDLE), HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);

    BOOL created = CreateProcessW(
        NULL, command, NULL, NULL, TRUE,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
        NULL, NULL, &startup, &process
    );
    free(command);
    if (!created) {
        CloseHandle(job);
        return 68;
    }
    if (!AssignProcessToJobObject(job, process.hProcess)) {
        TerminateProcess(process.hProcess, 1);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseHandle(job);
        return 69;
    }
    if (ResumeThread(process.hThread) == (DWORD)-1) {
        TerminateJobObject(job, 1);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseHandle(job);
        return 70;
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hProcess);
    CloseHandle(job);
    return (int)exit_code;
}
