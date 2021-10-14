// cppimport

/**
 * Naive implementations of string algorithms based on Gusfield, 1997.
 * I.e. There's plenty of room for improvement.
 *
*/


#include <algorithm>
#include <codecvt>
#include <cstddef>
#include <exception>
#include <iostream>
#include <iterator>
#include <limits>
#include <locale>
#include <numeric>
#include <sstream>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

/**
 * The character used to represent gaps in alignment output.
 */
const char32_t gap_char = U'⋄';

// This is a utility function for converting a string from UTF-32 to UTF-8
std::string convert_32_8(const std::u32string &bytes) {
    std::wstring_convert<std::codecvt_utf8<char32_t>,char32_t> conv;
    return conv.to_bytes(bytes);
}

// This is a utility function for converting a string from UTF-8 to UTF-32
std::u32string convert_8_32(const std::string &wide) {
    std::wstring_convert<std::codecvt_utf8<char32_t>,char32_t> conv;
    return conv.from_bytes(wide);
}

/**
 * Compute the Levenshtein distance for 2 strings.
 *
 * @param str1 Is a string to compare.
 * @param str2 The other string to compare.
 * @return The Levenshtein distance as an integer. The lower the number the more
 * similar the strings.
 */
long levenshtein(std::u32string& str1, std::u32string& str2) {
    const long len1 = str1.length();
    const long len2 = str2.length();

    if (len1 == 0) { return len2; }
    if (len2 == 0) { return len1; }

    std::vector<long> dist(len2 + 1);
    std::iota(dist.begin(), dist.end(), 0);

    for (long r = 0; r < len1; ++r) {
        long prev_dist = r;
        for (long c = 0; c < len2; ++c) {
            dist[c + 1] = std::min({
                std::exchange(prev_dist, dist[c + 1]) + (str1[r] == str2[c] ? 0 : 1),
                dist[c] + 1,
                dist[c + 1] + 1
            });
        }
    }
    return dist[len2];
}

/**
 * Compute a Levenshtein distance for every pair of strings in list.
 *
 * @param strings A list of strings to compare.
 * @return A sorted list of tuples. The tuple contains:
 *     - The Levenshtein distance of the pair of strings.
 *     - The index of the first string compared.
 *     - The index of the second string compared.
 * The tuples are sorted by distance.
 */
std::vector<std::tuple<long, long, long>>
levenshtein_all(std::vector<std::u32string> strings) {
    const long len = strings.size();

    std::vector<std::tuple<long, long, long>> results;

    for (long r = 0; r < len - 1; ++r) {
        for (long c = r + 1; c < len; ++c) {
            auto dist = levenshtein(strings[r], strings[c]);
            results.push_back(std::make_tuple(dist, r, c));
        }
    }

    std::stable_sort(results.begin(), results.end(),
        [](auto const &t1, auto const &t2) {
            return std::get<0>(t1) < std::get<0>(t2);
        });

    return results;
}

// Structures supporting the align_all() function.
enum TraceDir { none, diag, up, left };
struct Trace {
    float val;
    float up;
    float left;
    TraceDir dir;
    Trace(): val(0.0), up(0.0), left(0.0), dir(none) {}
};
typedef std::vector<std::vector<Trace>> TraceMatrix;

/**
 * Create a multiple sequence alignment of a set of similar short text fragments.
 * That is if I am given a set of strings like:
 *
 *     MOJAVE DESERT, PROVIDENCE MTS.: canyon above
 *     E. MOJAVE DESERT , PROVIDENCE MTS . : canyon above
 *     E MOJAVE DESERT PROVTDENCE MTS. # canyon above
 *     Be ‘MOJAVE DESERT, PROVIDENCE canyon “above
 *
 * I should get back something similar to the following. The exact return value
 * will depend on the substitution matrix, gap, and skew penalties passed to the
 * function.
 *
 *     ⋄⋄⋄⋄MOJAVE DESERT⋄, PROVIDENCE MTS⋄⋄.: canyon⋄⋄⋄⋄⋄⋄⋄
 *     E⋄. MOJAVE DESERT , PROVIDENCE MTS . : canyon⋄⋄⋄⋄⋄⋄⋄
 *     E⋄⋄ MOJAVE DESERT⋄⋄ PROVTDENCE MTS⋄. # canyon⋄⋄⋄⋄⋄⋄⋄
 *     Be ‘MOJAVE DESERT⋄, PROVIDENCE⋄⋄⋄⋄⋄⋄⋄⋄ canyon “above
 *
 * Where "⋄" characters are used to represent gaps in the alignments.
 *
 * @param strings A list of strings to align.
 * @param weight The substitution matrix given as a map, with the key as a two
 * character string representing the two character being substituted. Symmetry
 * is assumed so you only need to give the lexically first of a pair, i.e. for
 * "ab" and "ba" you only need to send in "ab". The value of the map is the
 * cost of substituting the two characters.
 * @param gap The gap open penalty for alignments. This is typically negative.
 * @param skew The gap extension penalty for the alignments. Also negative.
 *
 */
// TODO Make sure that pybind11 strings and weight matrix are not copied every time
std::vector<std::u32string>
align_all(
        std::vector<std::u32string>& strings,
        std::unordered_map<std::u32string, float>& weight,
        float gap,
        float skew
) {
    if (strings.size() < 1) {
        throw std::invalid_argument("You must enter at least one string.");
    }
    std::cout.precision(2);

    std::vector<std::u32string> results;

    results.push_back(strings[0]);

    for (size_t s = 1; s < strings.size(); ++s) {
        // Build the matrix
        size_t rows = results[0].length();
        size_t cols = strings[s].length();

        TraceMatrix trace(rows + 1, std::vector<Trace>(cols + 1));

        float g = gap;
        for (size_t r = 1; r <= rows; ++r) {
            trace[r][0].val = g;
            trace[r][0].up = g;
            trace[r][0].left = g;
            trace[r][0].dir = up;
            g += skew;
        }

        g = gap;
        for (size_t c = 1; c <= cols; ++c) {
            trace[0][c].val = g;
            trace[0][c].left = g;
            trace[0][c].up = g;
            trace[0][c].dir = left;
            g += skew;
        }

        for (size_t r = 1; r <= rows; ++r) {
            for (size_t c = 1; c <= cols; ++c) {
                Trace& cell = trace[r][c];
                Trace& cell_up = trace[r-1][c];
                Trace& cell_left = trace[r][c-1];

                cell.up = std::max({cell_up.up + skew, cell_up.val + gap});
                cell.left = std::max({cell_left.left + skew, cell_left.val + gap});

                float diagonal = std::numeric_limits<float>::lowest();
                for (size_t k = 0; k < results.size(); ++k) {
                    char32_t results_char = results[k][r-1];
                    char32_t strings_char = strings[s][c-1];

                    if (results_char == gap_char) { continue; }

                    if (results_char > strings_char) {
                        std::swap(strings_char, results_char);
                    }

                    std::u32string key = U"";
                    key += results_char;
                    key += strings_char;
                    float value;
                    try {
                        value = weight.at(key);
                    } catch (std::out_of_range& e) {
                        std::stringstream err;
                        err << "Either of '" << convert_32_8(key)
                            << "' these characters are missing from the "
                            << "substitution matrix.";
                        throw std::invalid_argument(err.str());
                    }
                    diagonal = value > diagonal ? value : diagonal;
                }
                diagonal += trace[r-1][c-1].val;
                cell.val = std::max({diagonal, cell.up, cell.left});

                if (cell.val == diagonal) {
                    cell.dir = diag;
                } else if (cell.val == cell.up) {
                    cell.dir = up;
                } else {
                    cell.dir = left;
                }
            }
        }

        // Trace-back
        long r = rows;
        long c = cols;
        std::u32string new_string;

        std::vector<std::u32string> new_results;
        for (size_t k = 0; k < results.size(); ++k) {
            new_results.push_back(U"");
        }

        while (true) {
            Trace cell = trace[r][c];
            if (cell.dir == none) {
                break;
            }

            if (cell.dir == diag) {
                for (size_t k = 0; k < results.size(); ++k) {
                    new_results[k] += results[k][r-1];
                }
                new_string += strings[s][c-1];
                --r;
                --c;
            } else if (cell.dir == up) {
                for (size_t k = 0; k < results.size(); ++k) {
                    new_results[k] += results[k][r-1];
                }
                new_string += gap_char;
                --r;
            } else {
                for (size_t k = 0; k < results.size(); ++k) {
                    new_results[k] += gap_char;
                }
                new_string += strings[s][c-1];
                --c;
            }
        }
        new_results.push_back(new_string);
        // TODO prevent string reversals with a better use of indexing
        results.clear();
        for (auto s : new_results) {
            std::reverse(s.begin(), s.end());
            results.push_back(s);
        }
    }

    return results;
}


PYBIND11_MODULE(string_align, m) {
    m.doc() = "Align multiple strings.";
    m.def("align_all", &align_all, "Get the alignment string for a pair of strings.");
    m.def("levenshtein", &levenshtein, "Get the levenshtein distance for 2 strings.");
    m.def("levenshtein_all", &levenshtein_all,
        "Get the levenshtein distance for all pairs of strings in the list.");
}


/*
<%
cfg['compiler_args'] = ['-std=c++17']
setup_pybind11(cfg)
%>
*/
