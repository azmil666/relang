/**
 * Matrix Digital Rain
 * Migrated to Node.js
 */

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const randint = (min, max) => {
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

class Matrix {
    static MATRIX_CHARS = [
        "- ", "* ", "% ", "& ", "# ", "@ ", "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 ", "0 ",
        "ア", "ィ", "イ", "ゥ", "ウ", "ェ", "エ", "ォ", "オ", "カ", "ガ", "キ", "ギ", "ク", "グ", "ケ", "ゲ", "コ",
        "ゴ", "サ", "ザ", "シ", "ジ", "ス", "ズ", "セ", "ゼ", "ソ", "ゾ", "タ", "ダ", "チ", "ヂ", "ッ", "ツ", "ヅ", "テ"
    ];
    static TERMINAL_COLOURS = ["22", "28"];

    constructor(screen_width = 150, line_count = 750, line_speed = 0.1) {
        this._screen_width = screen_width;
        this._line_count = line_count;
        this._line_speed = line_speed;
        this.line_array = {};
    }

    _getTextColourLightGreenChar() {
        return "\x1b[38;5;15m";
    }

    _getTextColourRandomChar() {
        const randomIndex = randint(0, 1);
        return "\x1b[38;5;" + Matrix.TERMINAL_COLOURS[randomIndex] + "m";
    }

    _getCharacter() {
        const total = Matrix.MATRIX_CHARS.length;
        const randomIndex = randint(0, (total - 1));
        return Matrix.MATRIX_CHARS[randomIndex];
    }

    _setScreenLineArray() {
        for (let i = 0; i < this._screen_width; i++) {
            this.line_array[i] = 1;
        }
    }

    async startMatrix() {
        this._setScreenLineArray();
        
        for (let l = 0; l < this._line_count; l++) {
            let line = "";

            for (let [m, n] of Object.entries(this.line_array)) {
                if (n === 1 || n === 2) {
                    if (n === 2) {
                        line = line + this._getTextColourLightGreenChar() + this._getCharacter();
                        this.line_array[m] = 1;
                    } else {
                        line = line + this._getTextColourRandomChar() + this._getCharacter();
                    }
                    
                    if (1 === randint(1, 30)) {
                        this.line_array[m] = 0;
                    }
                } else {
                    line = line + this._getTextColourRandomChar() + " ";
                    if (1 === randint(1, 60)) {
                        this.line_array[m] = 2;
                    }
                }
            }

            console.log(line);
            await sleep(this._line_speed * 1000);
        }
    }
}

if (require.main === module) {
    const matrix = new Matrix();
    matrix.startMatrix();
}