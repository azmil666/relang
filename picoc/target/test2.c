#include <stdio.h>
int main() {
    int x = 1;
    if (x < 10) {
        if (x % 2 == 0) printf("low even\n");
        else printf("low odd\n");
    } else if (x < 20) {
        printf("medium\n");
    } else {
        if (x % 5 == 0) printf("high mult 5\n");
        else printf("high other\n");
    }
    return 0;
}
