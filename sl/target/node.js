/**
 * SL (Steam Locomotive) for Node.js
 * Migrated from C / Python implementation
 */

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// --- CONSTANTS ---
const D51HEIGHT = 10, D51FUNNEL = 7, D51LENGTH = 83, D51PATTERNS = 6;
const D51STR1 = "      ====        ________                ___________ ";
const D51STR2 = "  _D _|  |_______/        \\__I_I_____===__|_________| ";
const D51STR3 = "   |(_)---  |   H\\________/ |   |        =|___ ___|   ";
const D51STR4 = "   /     |  |   H  |  |     |   |         ||_| |_||   ";
const D51STR5 = "  |      |  |   H  |__--------------------| [___] |   ";
const D51STR6 = "  | ________|___H__/__|_____/[][]~\\_______|       |   ";
const D51STR7 = "  |/ |   |-----------I_____I [][] []  D   |=======|__ ";
const D51WHL11 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ";
const D51WHL12 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ";
const D51WHL13 = "  \\_/      \\O=====O=====O=====O_/      \\_/            ";
const D51WHL21 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ";
const D51WHL22 = " |/-=|___|=O=====O=====O=====O   |_____/~\\___/        ";
const D51WHL23 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            ";
const D51WHL31 = "__/ =| o |=-O=====O=====O=====O \\ ____Y___________|__ ";
const D51WHL32 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ";
const D51WHL33 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            ";
const D51WHL41 = "__/ =| o |=-~O=====O=====O=====O\\ ____Y___________|__ ";
const D51WHL42 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ";
const D51WHL43 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            ";
const D51WHL51 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ";
const D51WHL52 = " |/-=|___|=   O=====O=====O=====O|_____/~\\___/        ";
const D51WHL53 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            ";
const D51WHL61 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ ";
const D51WHL62 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        ";
const D51WHL63 = "  \\_/      \\_O=====O=====O=====O/      \\_/            ";
const D51DEL   = "                                                      ";
const COAL01 = "                              ";
const COAL02 = "                              ";
const COAL03 = "    _________________         ";
const COAL04 = "   _|                \\_____A  ";
const COAL05 = " =|                        |  ";
const COAL06 = " -|                        |  ";
const COAL07 = "__|________________________|_ ";
const COAL08 = "|__________________________|_ ";
const COAL09 = "   |_D__D__D_|  |_D__D__D_|   ";
const COAL10 = "    \\_/   \\_/    \\_/   \\_/    ";
const COALDEL  = "                              ";

const LOGOHEIGHT = 6, LOGOFUNNEL = 4, LOGOLENGTH = 84, LOGOPATTERNS = 6;
const LOGO1 = "     ++      +------ ";
const LOGO2 = "     ||      |+-+ |  ";
const LOGO3 = "   /---------|| | |  ";
const LOGO4 = "  + ========  +-+ |  ";
const LWHL11 = " _|--O========O~\\-+  ";
const LWHL12 = "//// \\_/      \\_/    ";
const LWHL21 = " _|--/O========O\\-+  ";
const LWHL22 = "//// \\_/      \\_/    ";
const LWHL31 = " _|--/~O========O-+  ";
const LWHL32 = "//// \\_/      \\_/    ";
const LWHL41 = " _|--/~\\------/~\\-+  ";
const LWHL42 = "//// \\_O========O    ";
const LWHL51 = " _|--/~\\------/~\\-+  ";
const LWHL52 = "//// \\O========O/    ";
const LWHL61 = " _|--/~\\------/~\\-+  ";
const LWHL62 = "//// O========O_/    ";
const LCOAL1 = "____                 ";
const LCOAL2 = "|   \\@@@@@@@@@@@     ";
const LCOAL3 = "|    \\@@@@@@@@@@@@@_ ";
const LCOAL4 = "|                  | ";
const LCOAL5 = "|__________________| ";
const LCOAL6 = "   (O)       (O)     ";
const LCAR1  = "____________________ ";
const LCAR2  = "|  ___ ___ ___ ___ | ";
const LCAR3  = "|  |_| |_| |_| |_| | ";
const LCAR4  = "|__________________| ";
const LCAR5  = "|__________________| ";
const LCAR6  = "   (O)        (O)    ";
const DELLN  = "                     ";

const C51HEIGHT = 11, C51FUNNEL = 7, C51LENGTH = 87, C51PATTERNS = 6;
const C51DEL = "                                                       ";
const C51STR1 = "        ___                                            ";
const C51STR2 = "       _|_|_  _     __       __             ___________";
const C51STR3 = "    D__/   \\_(_)___|  |__H__|  |_____I_Ii_()|_________|";
const C51STR4 = "     | `---'   |:: `--'  H" + "  `--'         |  |___ ___|  ";
const C51STR5 = "    +|~~~~~~~~++::~~~~~~~H" + "~~+=====+~~~~~~|~~||_| |_||  ";
const C51STR6 = "    ||        | ::       H" + "  +=====+      |  |::  ...|  ";
const C51STR7 = "|    | _______|_::-----------------[][]-----|       |  ";
const C51WH61 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH62 = "------'|oOo|==[]=-     ||      ||      |  ||=======_|__";
const C51WH63 = "/~\\____|___|/~\\_|   O=======O=======O  |__|+-/~\\_|     ";
const C51WH64 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";
const C51WH51 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH52 = "------'|oOo|===[]=-    ||      ||      |  ||=======_|__";
const C51WH53 = "/~\\____|___|/~\\_|    O=======O=======O |__|+-/~\\_|     ";
const C51WH54 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";
const C51WH41 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH42 = "------'|oOo|===[]=- O=======O=======O  |  ||=======_|__";
const C51WH43 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ";
const C51WH44 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";
const C51WH31 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH32 = "------'|oOo|==[]=- O=======O=======O   |  ||=======_|__";
const C51WH33 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ";
const C51WH34 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";
const C51WH21 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH22 = "------'|oOo|=[]=- O=======O=======O    |  ||=======_|__";
const C51WH23 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     ";
const C51WH24 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";
const C51WH11 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__";
const C51WH12 = "------'|oOo|=[]=-      ||      ||      |  ||=======_|__";
const C51WH13 = "/~\\____|___|/~\\_|  O=======O=======O   |__|+-/~\\_|     ";
const C51WH14 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       ";

// --- ENGINE LOGIC ---

let ACCIDENT = 0, LOGO = 0, FLY = 0, C51 = 0, DANCE = 0, RAND = 0;
let COLS = 83, LINES = 47, N = 0;
let output_map = [];

const sl_patterns = [
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL11, LWHL12, DELLN],
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL21, LWHL22, DELLN],
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL31, LWHL32, DELLN],
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL41, LWHL42, DELLN],
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL51, LWHL52, DELLN],
    [LOGO1, LOGO2, LOGO3, LOGO4, LWHL61, LWHL62, DELLN]
];
const coal_pattern = [LCOAL1, LCOAL2, LCOAL3, LCOAL4, LCOAL5, LCOAL6, DELLN];
const car_pattern = [LCAR1, LCAR2, LCAR3, LCAR4, LCAR5, LCAR6, DELLN];

const d51_patterns = [
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL11, D51WHL12, D51WHL13, D51DEL],
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL21, D51WHL22, D51WHL23, D51DEL],
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL31, D51WHL32, D51WHL33, D51DEL],
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL41, D51WHL42, D51WHL43, D51DEL],
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL51, D51WHL52, D51WHL53, D51DEL],
    [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL61, D51WHL62, D51WHL63, D51DEL]
];
const d51_coal = [COAL01, COAL02, COAL03, COAL04, COAL05, COAL06, COAL07, COAL08, COAL09, COAL10, COALDEL];

const c51_patterns = [
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH11, C51WH12, C51WH13, C51WH14, C51DEL],
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH21, C51WH22, C51WH23, C51WH24, C51DEL],
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH31, C51WH32, C51WH33, C51WH34, C51DEL],
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH41, C51WH42, C51WH43, C51WH44, C51DEL],
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH51, C51WH52, C51WH53, C51WH54, C51DEL],
    [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH61, C51WH62, C51WH63, C51WH64, C51DEL]
];
const c51_coal = [COALDEL, COAL01, COAL02, COAL03, COAL04, COAL05, COAL06, COAL07, COAL08, COAL09, COAL10, COALDEL];

function count() {
    let min = 0, offset = 21;
    if (LOGO >= 1) min = -LOGOLENGTH - 1 - offset * (LOGO - 1);
    else if (C51 === 1) min = -C51LENGTH - 1;
    else min = -D51LENGTH - 1;
    return min;
}

function addchModify(y, x, c) {
    if (y < 0 || x < 0 || x >= COLS || y >= LINES) return -1;
    output_map[y * (COLS + 1) + x] = c;
    return 0;
}

function my_mvaddstr(y, x, str) {
    for (let i = 0; i < str.length; i++, x++) {
        if (x < 0) continue;
        if (addchModify(y, x, str[i]) === -1) return -1;
    }
    return 0;
}

function option(str) {
    for (let i = 0; i < str.length; i++) {
        if (str[i] === '-') continue;
        switch (str[i]) {
            case 'l': LOGO += 1; break;
            case 'a': ACCIDENT = 1; break;
            case 'F': FLY = 1; break;
            case 'c': C51 = 1; break;
            case 'd': DANCE = 1; break;
            case 'r': RAND = 1; break;
        }
    }
}

function windowInit(c, l, arg) {
    COLS = c; LINES = l;
    ACCIDENT = LOGO = FLY = C51 = DANCE = RAND = 0;
    option(arg);

    if (RAND === 1) {
        ACCIDENT |= Math.floor(Math.random() * 2);
        LOGO |= Math.floor(Math.random() * 2);
        FLY |= Math.floor(Math.random() * 2);
        C51 |= Math.floor(Math.random() * 2);
        DANCE |= Math.floor(Math.random() * 2);
    }
    N = -count() + COLS - 1;

    output_map = new Array(LINES * (COLS + 1)).fill(' ');
    for (let x = 0; x < LINES; ++x) {
        output_map[x * (COLS + 1) + COLS] = '\n';
    }
    output_map[LINES * (COLS + 1) - 1] = '';
}

function add_man(y, x) {
    const man = [["", "(O)"], ["Help!", "\\O/"]];
    for (let i = 0; i < 2; ++i) {
        my_mvaddstr(y + i, x, man[Math.floor((LOGOLENGTH + x) / 12) % 2][i]);
    }
}

function add_fdancer(y, x) {
    const fdancer = [["\\\\0", "/\\", "|\\"], ["0//", "/\\", "/|"]];
    const Efdancer = [["   ", "  ", "  "], ["   ", "  ", "  "]];
    for (let i = 0; i < 3; ++i) {
        my_mvaddstr(y + i, x + 1, Efdancer[Math.floor((LOGOLENGTH + x) / 12) % 2][i]);
        my_mvaddstr(y + i, x, fdancer[Math.floor((LOGOLENGTH + x) / 12) % 2][i]);
    }
}

function add_mdancer(y, x) {
    const mdancer = [["_O_", " #", "/\\"], ["(0)", " #", "/\\"], ["(O_", " #", "/\\"]];
    const Emdancer = [["   ", "  ", "  "], ["   ", "  ", "  "], ["   ", "  ", "  "]];
    for (let i = 0; i < 3; ++i) {
        my_mvaddstr(y + i, x + 1, Emdancer[Math.floor((LOGOLENGTH + x) / 12) % 3][i]);
        my_mvaddstr(y + i, x, mdancer[Math.floor((LOGOLENGTH + x) / 12) % 3][i]);
    }
}

// Minimal smoke state
let smoke_sum = 0;
const S = new Array(1000).fill(0).map(() => ({ y: 0, x: 0, ptrn: 0, kind: 0 }));

function add_smoke(y, x) {
    const Smoke = [
        ["(   )", "(    )", "(    )", "(   )", "(  )", "(  )", "( )", "( )", "()", "()", "O", "O", "O", "O", "O", " "],
        ["(@@@)", "(@@@@)", "(@@@@)", "(@@@)", "(@@)", "(@@)", "(@)", "(@)", "@@", "@@", "@", "@", "@", "@", "@", " "]
    ];
    const Eraser = [
        "     ", "      ", "      ", "     ", "    ", "    ", "   ", "   ", "  ", "  ", " ", " ", " ", " ", " ", " "
    ];
    const dy = [2, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const dx = [-2, -1, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3];

    if (x % 4 === 0) {
        for (let i = 0; i < smoke_sum; ++i) {
            my_mvaddstr(S[i].y, S[i].x, Eraser[S[i].ptrn]);
            S[i].y -= dy[S[i].ptrn];
            S[i].x += dx[S[i].ptrn];
            S[i].ptrn += (S[i].ptrn < 15) ? 1 : 0;
            my_mvaddstr(S[i].y, S[i].x, Smoke[S[i].kind][S[i].ptrn]);
        }
        my_mvaddstr(y, x, Smoke[smoke_sum % 2][0]);
        S[smoke_sum].y = y; S[smoke_sum].x = x;
        S[smoke_sum].ptrn = 0; S[smoke_sum].kind = smoke_sum % 2;
        smoke_sum++;
    }
}

function add_sl(x) {
    let y = Math.floor(LINES / 2) - 3;
    let py1 = 0, py2 = 0, py3 = 0, offset = 21, yoffset = 0;

    if (FLY === 1) {
        y = Math.floor(x / 6) + LINES - Math.floor(COLS / 6) - LOGOHEIGHT;
        py1 = 2; py2 = 4; py3 = 6;
    }
    for (let i = 0; i <= LOGOHEIGHT; ++i) {
        my_mvaddstr(y + i, x, sl_patterns[Math.floor((LOGOLENGTH + offset * (LOGO - 1) + x) / 3) % LOGOPATTERNS][i]);
        my_mvaddstr(y + i + py1, x + 21, coal_pattern[i]);
        for (let j = 0; j <= LOGO; j++) {
            yoffset = 2 * j * FLY;
            my_mvaddstr(y + i + py3 + yoffset, x + 42 + offset * j, car_pattern[i]);
        }
    }
    if (ACCIDENT === 1) {
        add_man(y + 1, x + 14);
        for (let j = 0; j <= LOGO; j++) {
            yoffset = FLY * (2 + 2 * j);
            add_man(y + 1 + py2 + yoffset, x + 45 + offset * j);
            add_man(y + 1 + py2 + yoffset, x + 53 + offset * j);
        }
    }
    if (DANCE === 1 && ACCIDENT === 0 && FLY === 0) {
        add_mdancer(y - 2, x + 21);
        for (let j = 0; j <= LOGO; j++) {
            add_mdancer(y + py2 - 2, x + 45 + offset * j);
            add_mdancer(y + py2 - 2, x + 50 + offset * j);
            add_mdancer(y + py2 - 2, x + 55 + offset * j);
        }
    }
    add_smoke(y - 1, x + LOGOFUNNEL);
}

function add_D51(x) {
    let y = Math.floor(LINES / 2) - 5;
    let dy = 0;

    if (FLY === 1) {
        y = Math.floor(x / 7) + LINES - Math.floor(COLS / 7) - D51HEIGHT;
        dy = 1;
    }
    for (let i = 0; i <= D51HEIGHT; ++i) {
        my_mvaddstr(y + i, x, d51_patterns[(D51LENGTH + x) % D51PATTERNS][i]);
        my_mvaddstr(y + i + dy, x + 53, d51_coal[i]);
    }
    if (ACCIDENT === 1) {
        add_man(y + 2, x + 43);
        add_man(y + 2, x + 47);
    }
    if (DANCE === 1 && ACCIDENT === 0 && FLY === 0) {
        add_mdancer(y - 2, x + 43); add_fdancer(y - 2, x + 48);
    }
    add_smoke(y - 1, x + D51FUNNEL);
}

function add_C51(x) {
    let y = Math.floor(LINES / 2) - 5;
    let dy = 0;

    if (FLY === 1) {
        y = Math.floor(x / 7) + LINES - Math.floor(COLS / 7) - C51HEIGHT;
        dy = 1;
    }
    for (let i = 0; i <= C51HEIGHT; ++i) {
        my_mvaddstr(y + i, x, c51_patterns[(C51LENGTH + x) % C51PATTERNS][i]);
        my_mvaddstr(y + i + dy, x + 55, c51_coal[i]);
    }
    if (ACCIDENT === 1) {
        add_man(y + 3, x + 45);
        add_man(y + 3, x + 49);
    }
    if (DANCE === 1 && ACCIDENT === 0 && FLY === 0) {
        add_mdancer(y - 1, x + 45); add_fdancer(y - 1, x + 50);
    }
    add_smoke(y - 1, x + C51FUNNEL);
}

function mapModify(mod) {
    let x = -mod + COLS - 1;
    if (LOGO >= 1) add_sl(x);
    else if (C51 === 1) add_C51(x);
    else add_D51(x);
}

async function startSL() {
    // Mimic stty size or default to 83x47
    const cols = process.stdout.columns || 83;
    const lines = process.stdout.rows || 47;
    const args = process.argv.slice(2).join(' ');

    windowInit(cols, lines, args);

    for (let x = 0; x < N; ++x) {
        mapModify(x);
        // Print the buffer and scroll terminal (matching python's print behaviour)
        console.log(output_map.join(''));
        await sleep(40); // 0.04s loop
    }
}

if (require.main === module) {
    startSL();
}