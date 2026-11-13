conductivity_profile = (
    "chi_boundary_left",
    "chi_boundary_right",
    "chi_frac_left",
    "chi_frac_right",
    "chi_barrier_centre",
    "chi_barrier_height",
    "chi_barrier_width",
    "chi_gap_left",
    "chi_gap_right",
)

diffusivity_profile = (
    "D_boundary_left",
    "D_boundary_right",
    "D_frac_left",
    "D_frac_right",
    "D_barrier_centre",
    "D_barrier_height",
    "D_barrier_width",
    "D_gap_left",
    "D_gap_right",
)

required_parameters = {
    "chi_boundary_left",
    "chi_boundary_right",
    "chi_frac_left",
    "chi_frac_right",
    "chi_barrier_centre",
    "chi_barrier_height",
    "chi_barrier_width",
    "chi_gap_left",
    "chi_gap_right",
    "D_boundary_left",
    "D_boundary_right",
    "D_frac_left",
    "D_frac_right",
    "D_barrier_centre",
    "D_barrier_height",
    "D_barrier_width",
    "D_gap_left",
    "D_gap_right",
}

divertor_transport = ("D_div", "chi_div")

dataframe_columns = (
    "iteration",
    "gaussian_logprob",
    "cauchy_logprob",
    "laplace_logprob",
    "logistic_logprob",
    "error_model",
    "cross_validation",
    "acquisition_function",
    "prediction_mean",
    "prediction_error",
    "convergence_metric",
)

# the parameters a step profile (Solps profile_shape="step") uses, in the
# order step_profile_knots takes them; the other profile parameters are ignored
step_conductivity_profile = (
    "chi_boundary_left",
    "chi_boundary_right",
    "chi_barrier_height",
)

step_diffusivity_profile = (
    "D_boundary_left",
    "D_boundary_right",
    "D_barrier_height",
)
