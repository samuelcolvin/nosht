import React from 'react'


export const YoutubePlayer = ({vid, ...props}) => (
    <div {...props}>
        <div className='video-wrapper youtube mt-3 mb-4 aspectRatio_16_9_Style'>
            <iframe
                className='aspectRatio_fill_Style'
                src={`https://www.youtube.com/embed/${vid}`}
                frameBorder="0"
                title={`youtube-iframe-${vid}`}
            />
        </div>
    </div>
)
export default YoutubePlayer
