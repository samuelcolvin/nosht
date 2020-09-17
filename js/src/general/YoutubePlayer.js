import React from 'react'


export const YoutubePlayer = ({vid, ...props}) => (
    <div {...props}>
        <div className={`video-wrapper youtube mt-3 mb-4`} style={aspectRatio_16_9_Style} >
            <iframe
                style={aspectRatio_fill_Style}
                src={`https://www.youtube.com/embed/${vid}`}
                frameBorder="0"
                title={`youtube-iframe-${vid}`}
            />
        </div>
    </div>
)
export default YoutubePlayer


const aspectRatio_16_9_Style = {
    position: "relative",
    paddingBottom: "56.25%",
    paddingTop: 25,
    height: 0
}

const aspectRatio_fill_Style = {
    position: "absolute",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%"
}
