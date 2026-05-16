"""
基础工具函数
"""

function spin_basis_state(config::Vector{Int})
    idx = 0
    for (i, s) in enumerate(config)
        idx += s * 2^(i-1)
    end
    return idx + 1
end

function index_to_config(idx::Int, N::Int)
    config = zeros(Int, N)
    idx -= 1
    for i in 1:N
        config[i] = idx & 1
        idx >>= 1
    end
    return config
end

function sz_value(bit::Int)
    return bit == 1 ? 0.5 : -0.5
end
