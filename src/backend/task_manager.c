#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include <ctype.h>
#include <string.h>
#include <unistd.h>

#define TABLE_SIZE 1024
#define MAX_PROCESSES 1024
#define MAX_GPUS 8
#define PATH_SIZE 256
#define NAME_SIZE 256
#define LINE_SIZE 512

typedef struct {
    int index;
    char name[NAME_SIZE];
    int utilization;        // GPU utilization %
    unsigned long mem_used; // Memory used in MB
    unsigned long mem_total;// Total memory in MB
    int temperature;        // Temperature in Celsius
    int power_usage;        // Power usage in Watts
    int power_limit;        // Power limit in Watts
} gpu_info;

typedef struct {
    int pid;
    unsigned long long last_cpu_time;           //stores last cpu time of each process
} cpu_record_time;

typedef struct {
    int pid;
    char name[NAME_SIZE];
    char state;
    float cpu_usage;
    int threads;
    unsigned long memory;
} process_info;


unsigned long long last_total_cpu_time = 0;          //stores last total cpu time
cpu_record_time cpu_table[TABLE_SIZE];               //stores pid and last total cpu time of each process
process_info plist[MAX_PROCESSES];                   // stores information of all processes
int p_count = 0;
int process_count = 0;


unsigned long long get_total_cpu_time(unsigned long long *delta);
int get_process_name(int pid, char *name, size_t size);
int get_process_state_and_times(int pid, char *state, unsigned long long *utime, unsigned long long *stime);
int get_process_threads(int pid);
float calculate_cpu_usage(int pid, unsigned long long cpu_time_per_process, unsigned long long delta_total_cpu_time);
unsigned long get_process_memory(int pid);

void read_process_info(void);
void clear_screen(void);

// Get total CPU time and calculate delta
unsigned long long get_total_cpu_time(unsigned long long *delta) {
    FILE *fp = fopen("/proc/stat", "r");
    if (fp == NULL) {
        *delta = 0;
        return 0;
    }
    
    unsigned long long user, nice, system, idle, total_cpu;
    fscanf(fp, "%*s %llu %llu %llu %llu", &user, &nice, &system, &idle);
    fclose(fp);
    
    total_cpu = user + nice + system + idle;
    
    if (last_total_cpu_time == 0) {
        last_total_cpu_time = total_cpu;
        *delta = 0;
    } else {
        *delta = total_cpu - last_total_cpu_time;
        last_total_cpu_time = total_cpu;
    }
    
    return total_cpu;
}

// Read process name from /proc/<pid>/comm

int get_process_name(int pid, char *name, size_t size) {
    char path[PATH_SIZE];
    snprintf(path, sizeof(path), "/proc/%d/comm", pid);
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) return -1;
    
    if (fgets(name, size, fp) == NULL) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    
    name[strcspn(name, "\n")] = '\0';
    return 0;
}

// Read process state and CPU times from /proc/<pid>/stat

int get_process_state_and_times(int pid, char *state, unsigned long long *utime, unsigned long long *stime) {
    char path[PATH_SIZE];
    snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) return -1;
    
    fscanf(fp, "%*d %*s %c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %llu %llu",
           state, utime, stime);
    fclose(fp);
    
    return 0;
}

// Read thread count from /proc/<pid>/status
int get_process_threads(int pid) {
    char path[PATH_SIZE];
    char line[LINE_SIZE];
    int threads = 0;
    
    snprintf(path, sizeof(path), "/proc/%d/status", pid);
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) return 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "Threads:", 8) == 0) {
            sscanf(line, "Threads: %d", &threads);
            break;
        }
    }
    fclose(fp);
    
    return threads;
}

// Calculate CPU usage for a process
float calculate_cpu_usage(int pid, unsigned long long cpu_time_per_process,
                         unsigned long long delta_total_cpu_time) {
    if (delta_total_cpu_time == 0 || process_count >= TABLE_SIZE) {
        return 0.0;
    }
    
    int i;
    for (i = 0; i < process_count; i++) {
        if (cpu_table[i].pid == pid) {
            break;
        }
    }
    
    // if process not in process_list
    if (i == process_count) {
        cpu_table[process_count].pid = pid;
        cpu_table[process_count].last_cpu_time = cpu_time_per_process;
        process_count++;
        return 0.0;
    }
    
    
    unsigned long long delta_cpu_per_process = cpu_time_per_process - cpu_table[i].last_cpu_time;
    int cores = sysconf(_SC_NPROCESSORS_ONLN);
    float cpu_usage = (delta_cpu_per_process * 100.0) / (delta_total_cpu_time * cores);
    
    cpu_table[i].last_cpu_time = cpu_time_per_process;
    
    return cpu_usage;
}

unsigned long get_process_memory(int pid){
    char path[PATH_SIZE];
    char line[LINE_SIZE];
    snprintf(path,sizeof(path),"/proc/%d/status",pid);

    FILE *fp = fopen(path,"r");
    if(fp==NULL)return 0;

    unsigned long memory=0;

    while(fgets(line,sizeof(line),fp)){
        if(strncmp(line,"VmRSS:",6)==0){
            sscanf(line,"VmRSS: %lu",&memory);              //memory value in kb
            break;
        }
    }
    fclose(fp);
        return memory;

}

// Get NVIDIA GPU information using nvidia-smi
int get_gpu_info(gpu_info *gpus, int max_gpus) {
    FILE *fp = popen("nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit --format=csv,noheader,nounits 2>/dev/null", "r");
    if (fp == NULL) {
        return 0;
    }

    int gpu_count = 0;
    char line[LINE_SIZE];

    while (fgets(line, sizeof(line), fp) != NULL && gpu_count < max_gpus) {
        gpu_info *g = &gpus[gpu_count];

        // Parse CSV: index, name, utilization, mem_used, mem_total, temp, power, power_limit
        char *token = strtok(line, ",");
        if (token) g->index = atoi(token);

        token = strtok(NULL, ",");
        if (token) {
            while (*token == ' ') token++; // trim leading space
            strncpy(g->name, token, NAME_SIZE - 1);
            g->name[NAME_SIZE - 1] = '\0';
            // Trim trailing whitespace
            char *end = g->name + strlen(g->name) - 1;
            while (end > g->name && (*end == ' ' || *end == '\n')) *end-- = '\0';
        }

        token = strtok(NULL, ",");
        if (token) g->utilization = atoi(token);

        token = strtok(NULL, ",");
        if (token) g->mem_used = atol(token);

        token = strtok(NULL, ",");
        if (token) g->mem_total = atol(token);

        token = strtok(NULL, ",");
        if (token) g->temperature = atoi(token);

        token = strtok(NULL, ",");
        if (token) g->power_usage = (int)atof(token);

        token = strtok(NULL, ",");
        if (token) {
            // Handle "[N/A]" case for power limit
            if (strstr(token, "N/A") != NULL) {
                g->power_limit = 0;
            } else {
                g->power_limit = (int)atof(token);
            }
        }

        gpu_count++;
    }

    pclose(fp);
    return gpu_count;
}

// Output GPU information
void output_gpu_info(void) {
    gpu_info gpus[MAX_GPUS];
    int gpu_count = get_gpu_info(gpus, MAX_GPUS);

    if (gpu_count > 0) {
        printf("GPU_START\n");
        for (int i = 0; i < gpu_count; i++) {
            printf("GPU|%d|%s|%d|%lu|%lu|%d|%d|%d\n",
                   gpus[i].index,
                   gpus[i].name,
                   gpus[i].utilization,
                   gpus[i].mem_used,
                   gpus[i].mem_total,
                   gpus[i].temperature,
                   gpus[i].power_usage,
                   gpus[i].power_limit);
        }
        printf("GPU_END\n");
        fflush(stdout);
    }
}


void read_process_info(void) {
    DIR *dir = opendir("/proc");
    if (dir == NULL) {
        printf("Error: Cannot open /proc directory\n");
        return;
    }
    
    unsigned long long delta_total_cpu;
    get_total_cpu_time(&delta_total_cpu);
    
    p_count = 0;
    struct dirent *entry;
    
    while ((entry = readdir(dir)) != NULL) {
        if (!isdigit(entry->d_name[0])) continue;
        if (p_count >= MAX_PROCESSES) break;
        
        int pid = atoi(entry->d_name);
        
        // process_name
        
        char name[NAME_SIZE];
        if (get_process_name(pid, name, sizeof(name)) != 0) continue;
        
        // process state and time
        
        char state;
        unsigned long long utime, stime;
        if (get_process_state_and_times(pid, &state, &utime, &stime) != 0) continue;
        
        // cpu usage
        
        float cpu_usage = calculate_cpu_usage(pid, utime + stime, delta_total_cpu);
        
        // thread_count
        
        int threads = get_process_threads(pid);
        
        unsigned long memory = get_process_memory(pid);
        
        // Store process information
        plist[p_count] = (process_info){
            .pid = pid,
            .state = state,
            .cpu_usage = cpu_usage,
            .threads = threads,
            .memory = memory
        };
        strncpy(plist[p_count].name, name, NAME_SIZE - 1);
        plist[p_count].name[NAME_SIZE - 1] = '\0';
        
        p_count++;
    }
    
    closedir(dir);
    
    // Sort by CPU usage (descending) to show most active processes first
    for (int i = 0; i < p_count - 1; i++) {
        for (int j = 0; j < p_count - i - 1; j++) {
            if (plist[j].cpu_usage < plist[j + 1].cpu_usage) {
                process_info temp = plist[j];
                plist[j] = plist[j + 1];
                plist[j + 1] = temp;
            }
        }
    }
    
    // Send ALL processes (no artificial limit to prevent flickering)
    for (int i = 0; i < p_count; i++) {
        printf("%d|%s|%c|%.2f|%lu|%d\n",
               plist[i].pid,
               plist[i].name,
               plist[i].state,
               plist[i].cpu_usage,
               plist[i].memory,
               plist[i].threads);
    }
    printf("END\n");
    fflush(stdout);
}



int main(void) {
    while (1) {
        read_process_info();
        output_gpu_info();
        sleep(2);
    }

    return 0;
}
