module PentamerChain

using ITensors
using ITensorMPS
using LinearAlgebra
using SparseArrays
using Printf
using JLD2

include("utils.jl")
include("hamiltonian.jl")
include("exact_diag.jl")
include("dmrg_solver.jl")
include("order_parameters.jl")
include("spectral.jl")

export pentamer_hamiltonian_matrix, pentamer_chain_hamiltonian
export diagonalize_pentamer, classify_states, total_spin_squared_matrix
export compute_ground_state, compute_ground_state_hires, compute_excited_state
export string_order_parameter, bipartite_entropy, spin_gap
export apply_Sq_operator, correction_vector_dsf, compute_dsf_spectrum

end
