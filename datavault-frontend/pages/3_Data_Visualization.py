import streamlit as st
import pandas as pd
import plotly.express as px
from dataset_handler import get_from_supabase, get_user_datasets

# Initialize session state if not already done
if 'authenticated' not in st.session_state:
    st.warning("Please login to access this page.")
    st.stop()

if not st.session_state.get('authenticated', False):
    st.warning("Please login to access this page.")
    st.stop()

if 'supabase' not in st.session_state:
    st.error("Error: Application not properly initialized. Please return to the home page.")
    st.stop()

# Page config
st.set_page_config(page_title="Data Visualization", page_icon="📈", layout="wide")

st.title("Data Visualization")

# Initialize session state for visualization
if 'current_viz_dataset' not in st.session_state:
    st.session_state.current_viz_dataset = None
if 'current_viz_df' not in st.session_state:
    st.session_state.current_viz_df = None

# Sidebar for dataset selection
with st.sidebar:
    st.header("Dataset Selection")
    datasets = get_user_datasets(st.session_state.supabase, st.session_state.user.id)
    
    if datasets:
        selected_dataset = st.selectbox(
            "Select a dataset to visualize",
            options=[d['name'] for d in datasets],
            format_func=lambda x: x.split('/')[-1]
        )
        
        if st.button("Load Dataset") or (selected_dataset != st.session_state.current_viz_dataset):
            selected_path = next(d['path'] for d in datasets if d['name'] == selected_dataset)
            df = get_from_supabase(st.session_state.supabase, selected_path)
            if df is not None:
                st.session_state.current_viz_dataset = selected_dataset
                st.session_state.current_viz_df = df
                st.success("Dataset loaded successfully!")
    else:
        st.info("No datasets available. Please upload a dataset first.")
        st.stop()

# Main content
if st.session_state.current_viz_df is not None:
    df = st.session_state.current_viz_df
    
    # Create tabs for different visualization types
    tab1, tab2, tab3 = st.tabs(["Basic Charts", "Statistical Plots", "Custom Visualization"])
    
    with tab1:
        st.header("Basic Charts")
        
        chart_type = st.selectbox(
            "Select chart type",
            ["Line Chart", "Bar Chart", "Scatter Plot", "Histogram"]
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            x_axis = st.selectbox("Select X-axis", df.columns)
            
            if chart_type != "Histogram":
                y_axis = st.selectbox("Select Y-axis", numeric_cols)
            
            if chart_type in ["Scatter Plot", "Line Chart"]:
                color_by = st.selectbox("Color by", ["None"] + list(df.columns))
        
        with col2:
            if chart_type == "Bar Chart":
                agg_func = st.selectbox(
                    "Aggregation function",
                    ["sum", "mean", "count", "min", "max"]
                )
            
            if chart_type != "Histogram":
                sort_by = st.selectbox(
                    "Sort by",
                    ["None", "X-axis", "Y-axis"]
                )
        
        # Generate the selected chart
        try:
            if chart_type == "Line Chart":
                fig = px.line(
                    df,
                    x=x_axis,
                    y=y_axis,
                    color=None if color_by == "None" else color_by,
                    title=f"{y_axis} vs {x_axis}"
                )
            
            elif chart_type == "Bar Chart":
                if agg_func == "count":
                    fig = px.bar(
                        df[x_axis].value_counts().reset_index(),
                        x="index",
                        y=x_axis,
                        title=f"Count of {x_axis}"
                    )
                else:
                    fig = px.bar(
                        df.groupby(x_axis).agg({y_axis: agg_func}).reset_index(),
                        x=x_axis,
                        y=y_axis,
                        title=f"{agg_func.capitalize()} of {y_axis} by {x_axis}"
                    )
            
            elif chart_type == "Scatter Plot":
                fig = px.scatter(
                    df,
                    x=x_axis,
                    y=y_axis,
                    color=None if color_by == "None" else color_by,
                    title=f"{y_axis} vs {x_axis}"
                )
            
            elif chart_type == "Histogram":
                fig = px.histogram(
                    df,
                    x=x_axis,
                    title=f"Distribution of {x_axis}"
                )
            
            # Update layout
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray'),
                yaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error generating chart: {str(e)}")
    
    with tab2:
        st.header("Statistical Plots")
        
        plot_type = st.selectbox(
            "Select plot type",
            ["Box Plot", "Violin Plot", "Distribution Plot"]
        )
        
        try:
            if plot_type == "Box Plot":
                numeric_col = st.selectbox("Select numeric column", df.select_dtypes(include=['int64', 'float64']).columns)
                category_col = st.selectbox("Group by (optional)", ["None"] + list(df.select_dtypes(include=['object']).columns))
                
                if category_col == "None":
                    fig = px.box(df, y=numeric_col, title=f"Box Plot of {numeric_col}")
                else:
                    fig = px.box(df, x=category_col, y=numeric_col, title=f"Box Plot of {numeric_col} by {category_col}")
            
            elif plot_type == "Violin Plot":
                numeric_col = st.selectbox("Select numeric column", df.select_dtypes(include=['int64', 'float64']).columns)
                category_col = st.selectbox("Group by (optional)", ["None"] + list(df.select_dtypes(include=['object']).columns))
                
                if category_col == "None":
                    fig = px.violin(df, y=numeric_col, title=f"Violin Plot of {numeric_col}")
                else:
                    fig = px.violin(df, x=category_col, y=numeric_col, title=f"Violin Plot of {numeric_col} by {category_col}")
            
            elif plot_type == "Distribution Plot":
                numeric_col = st.selectbox("Select numeric column", df.select_dtypes(include=['int64', 'float64']).columns)
                fig = px.histogram(
                    df,
                    x=numeric_col,
                    marginal="box",
                    title=f"Distribution of {numeric_col}"
                )
            
            # Update layout
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray'),
                yaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error generating plot: {str(e)}")
    
    with tab3:
        st.header("Custom Visualization")
        st.info("Coming soon! This section will allow you to create custom visualizations with more advanced options.") 