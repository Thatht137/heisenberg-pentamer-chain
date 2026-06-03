using JLD2
using Printf

function esc(s)
    replace(string(s), "&" => "&amp;", "<" => "&lt;", ">" => "&gt;")
end

function rgb_color(x)
    x = clamp(x, 0.0, 1.0)
    stops = [
        (0.00, (30, 35, 70)),
        (0.25, (40, 110, 150)),
        (0.50, (70, 170, 105)),
        (0.75, (235, 185, 65)),
        (1.00, (210, 55, 45)),
    ]
    for i in 1:(length(stops)-1)
        x0, c0 = stops[i]
        x1, c1 = stops[i+1]
        if x <= x1
            t = (x - x0) / (x1 - x0)
            r = round(Int, (1 - t) * c0[1] + t * c1[1])
            g = round(Int, (1 - t) * c0[2] + t * c1[2])
            b = round(Int, (1 - t) * c0[3] + t * c1[3])
            return @sprintf("#%02x%02x%02x", r, g, b)
        end
    end
    return "#d2372d"
end

function q_label(x)
    if isapprox(x, 0; atol=1e-8)
        return "0"
    elseif isapprox(x, pi/2; atol=1e-8)
        return "π/2"
    elseif isapprox(x, pi; atol=1e-8)
        return "π"
    elseif isapprox(x, 3pi/2; atol=1e-8)
        return "3π/2"
    elseif isapprox(x, 2pi; atol=1e-8)
        return "2π"
    end
    return @sprintf("%.2f", x)
end

function write_heatmap(path, q, w, S; alpha, beta, n_units, eta)
    width, height = 980, 680
    left, right, top, bottom = 86, 155, 56, 86
    pw = width - left - right
    ph = height - top - bottom
    nq, nw = size(S)
    smax = maximum(S)

    open(path, "w") do io
        println(io, """<svg xmlns="http://www.w3.org/2000/svg" width="$width" height="$height" viewBox="0 0 $width $height">""")
        println(io, """<rect width="100%" height="100%" fill="#ffffff"/>""")
        println(io, """<text x="$(width/2)" y="28" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">S(q, omega)</text>""")
        println(io, """<text x="$(width/2)" y="50" text-anchor="middle" font-family="Arial" font-size="13" fill="#555">alpha=$alpha, beta=$beta, N_units=$n_units, eta=$eta</text>""")

        cellw = pw / nq
        cellh = ph / nw
        for iq in 1:nq
            for iw in 1:nw
                x = left + (iq - 1) * cellw
                y = top + ph - iw * cellh
                c = rgb_color(S[iq, iw] / smax)
                println(io, """<rect x="$x" y="$y" width="$(cellw + 0.8)" height="$(cellh + 0.8)" fill="$c"/>""")
            end
        end

        println(io, """<rect x="$left" y="$top" width="$pw" height="$ph" fill="none" stroke="#222" stroke-width="1"/>""")

        for val in [0, pi/2, pi, 3pi/2, 2pi]
            x = left + (val - first(q)) / (last(q) - first(q)) * pw
            println(io, """<line x1="$x" y1="$top" x2="$x" y2="$(top+ph)" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1"/>""")
            println(io, """<text x="$x" y="$(top+ph+28)" text-anchor="middle" font-family="Arial" font-size="14">$(q_label(val))</text>""")
        end
        for val in range(first(w), last(w), length=7)
            y = top + ph - (val - first(w)) / (last(w) - first(w)) * ph
            println(io, """<line x1="$left" y1="$y" x2="$(left+pw)" y2="$y" stroke="#ffffff" stroke-opacity="0.25" stroke-width="1"/>""")
            println(io, """<text x="$(left-12)" y="$(y+5)" text-anchor="end" font-family="Arial" font-size="13">$(@sprintf("%.1f", val))</text>""")
        end

        println(io, """<text x="$(left + pw/2)" y="$(height-24)" text-anchor="middle" font-family="Arial" font-size="16">q</text>""")
        println(io, """<text transform="translate(24,$(top + ph/2)) rotate(-90)" text-anchor="middle" font-family="Arial" font-size="16">omega</text>""")

        cbx, cby, cbw, cbh = left + pw + 38, top, 24, ph
        for i in 0:180
            yy = cby + cbh - i * cbh / 180
            println(io, """<rect x="$cbx" y="$yy" width="$cbw" height="$(cbh/180 + 1)" fill="$(rgb_color(i/180))"/>""")
        end
        println(io, """<rect x="$cbx" y="$cby" width="$cbw" height="$cbh" fill="none" stroke="#222"/>""")
        for val in range(0, smax, length=6)
            y = cby + cbh - val / smax * cbh
            println(io, """<line x1="$(cbx+cbw)" y1="$y" x2="$(cbx+cbw+6)" y2="$y" stroke="#222"/>""")
            println(io, """<text x="$(cbx+cbw+10)" y="$(y+4)" font-family="Arial" font-size="12">$(@sprintf("%.2f", val))</text>""")
        end
        println(io, """<text x="$(cbx+12)" y="$(cby-12)" text-anchor="middle" font-family="Arial" font-size="14">S</text>""")
        println(io, "</svg>")
    end
end

function write_line_plot(path, xs, series; title, xlabel, ylabel)
    width, height = 900, 560
    left, right, top, bottom = 82, 36, 54, 76
    pw = width - left - right
    ph = height - top - bottom
    ymin = min(0.0, minimum(vcat([y for (_, y, _) in series]...)))
    ymax = maximum(vcat([y for (_, y, _) in series]...))
    ymax = ymax <= ymin ? ymin + 1 : ymax
    colors = ["#1b6ca8", "#d1495b", "#2a9d8f", "#f4a261", "#6d597a", "#4d908e"]

    xmap(x) = left + (x - first(xs)) / (last(xs) - first(xs)) * pw
    ymap(y) = top + ph - (y - ymin) / (ymax - ymin) * ph

    open(path, "w") do io
        println(io, """<svg xmlns="http://www.w3.org/2000/svg" width="$width" height="$height" viewBox="0 0 $width $height">""")
        println(io, """<rect width="100%" height="100%" fill="#ffffff"/>""")
        println(io, """<text x="$(width/2)" y="30" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">$(esc(title))</text>""")
        println(io, """<rect x="$left" y="$top" width="$pw" height="$ph" fill="#f8f8f8" stroke="#222"/>""")

        for val in range(first(xs), last(xs), length=6)
            x = xmap(val)
            println(io, """<line x1="$x" y1="$top" x2="$x" y2="$(top+ph)" stroke="#dddddd"/>""")
            println(io, """<text x="$x" y="$(top+ph+28)" text-anchor="middle" font-family="Arial" font-size="13">$(@sprintf("%.2f", val))</text>""")
        end
        for val in range(ymin, ymax, length=6)
            y = ymap(val)
            println(io, """<line x1="$left" y1="$y" x2="$(left+pw)" y2="$y" stroke="#dddddd"/>""")
            println(io, """<text x="$(left-10)" y="$(y+4)" text-anchor="end" font-family="Arial" font-size="13">$(@sprintf("%.2f", val))</text>""")
        end

        for (i, (_, ys, label)) in enumerate(series)
            color = colors[mod1(i, length(colors))]
            points = join(["$(xmap(xs[j])),$(ymap(ys[j]))" for j in eachindex(xs)], " ")
            println(io, """<polyline points="$points" fill="none" stroke="$color" stroke-width="2.4"/>""")
            lx, ly = left + pw - 150, top + 22 + 22 * (i - 1)
            println(io, """<line x1="$lx" y1="$ly" x2="$(lx+24)" y2="$ly" stroke="$color" stroke-width="2.4"/>""")
            println(io, """<text x="$(lx+32)" y="$(ly+5)" font-family="Arial" font-size="13">$(esc(label))</text>""")
        end

        println(io, """<text x="$(left + pw/2)" y="$(height-24)" text-anchor="middle" font-family="Arial" font-size="16">$(esc(xlabel))</text>""")
        println(io, """<text transform="translate(24,$(top + ph/2)) rotate(-90)" text-anchor="middle" font-family="Arial" font-size="16">$(esc(ylabel))</text>""")
        println(io, "</svg>")
    end
end

function main()
    file = joinpath("data", "dsf_spectrum.jld2")
    outdir = joinpath("data", "figures")
    mkpath(outdir)

    jldopen(file, "r") do f
        S = Array(f["S_qw"])
        q = collect(f["q_points"])
        w = collect(f["omega_range"])
        alpha = f["alpha"]
        beta = f["beta"]
        n_units = f["N_units"]
        eta = f["eta"]

        # 负数只来自浮点误差，绘图时裁到零
        S[S .< 0] .= 0.0

        write_heatmap(joinpath(outdir, "dsf_heatmap.svg"), q, w, S; alpha, beta, n_units, eta)

        iq_pi = argmin(abs.(q .- pi))
        write_line_plot(
            joinpath(outdir, "dsf_q_pi_cut.svg"),
            w,
            [(w, S[iq_pi, :], "q = π")];
            title="S(π, omega)",
            xlabel="omega",
            ylabel="S"
        )

        omega_ids = unique(round.(Int, range(1, length(w), length=5)))
        series = [(q, S[:, iw], "omega = $(@sprintf("%.2f", w[iw]))") for iw in omega_ids]
        write_line_plot(
            joinpath(outdir, "dsf_fixed_omega_cuts.svg"),
            q,
            series;
            title="Fixed omega cuts",
            xlabel="q",
            ylabel="S"
        )

        summary = joinpath(outdir, "dsf_summary.txt")
        open(summary, "w") do io
            idx = argmax(S)
            println(io, "size(S_qw) = ", size(S))
            println(io, "alpha = ", alpha)
            println(io, "beta = ", beta)
            println(io, "N_units = ", n_units)
            println(io, "eta = ", eta)
            println(io, "max = ", maximum(S))
            println(io, "max index = ", idx)
            println(io, "q at max = ", q[idx[1]])
            println(io, "omega at max = ", w[idx[2]])
            println(io, "min = ", minimum(S))
            println(io, "has NaN = ", any(isnan, S))
            println(io, "has Inf = ", any(isinf, S))
        end
    end

    println("图已保存到 data/figures/")
end

main()
