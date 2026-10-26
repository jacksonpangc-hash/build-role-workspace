#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <AppKit/AppKit.h>
#import <CoreVideo/CoreVideo.h>
int main(int argc,const char **argv){@autoreleasepool {
 if(argc!=2){fprintf(stderr,"Use a new empty synthetic output folder\n");return 64;}
 NSString *folder=[NSString stringWithUTF8String:argv[1]];
 [[NSFileManager defaultManager] createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:nil];
 if([[[NSFileManager defaultManager] contentsOfDirectoryAtPath:folder error:nil] count]>0)return 2;
 NSURL *url=[NSURL fileURLWithPath:[folder stringByAppendingPathComponent:@"silent-demo.mp4"]];
 if([[NSFileManager defaultManager] fileExistsAtPath:url.path])return 2;
 NSError *error=nil;
 AVAssetWriter *writer=[[AVAssetWriter alloc] initWithURL:url fileType:AVFileTypeMPEG4 error:&error];
 if(!writer){fprintf(stderr,"writer creation failed\n");return 3;}
 NSDictionary *settings=@{AVVideoCodecKey:AVVideoCodecTypeH264,AVVideoWidthKey:@320,AVVideoHeightKey:@180};
 AVAssetWriterInput *input=[AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo outputSettings:settings];
 NSDictionary *attributes=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_32ARGB),(id)kCVPixelBufferWidthKey:@320,(id)kCVPixelBufferHeightKey:@180};
 AVAssetWriterInputPixelBufferAdaptor *adaptor=[AVAssetWriterInputPixelBufferAdaptor assetWriterInputPixelBufferAdaptorWithAssetWriterInput:input sourcePixelBufferAttributes:attributes];
 [writer addInput:input];[writer startWriting];[writer startSessionAtSourceTime:kCMTimeZero];
 unsigned char colors[3][4]={{255,220,30,30},{255,30,180,30},{255,30,30,220}};
 for(int frame=0;frame<12;frame++){
  CVPixelBufferRef pixel=NULL;
  if(CVPixelBufferCreate(kCFAllocatorDefault,320,180,kCVPixelFormatType_32ARGB,NULL,&pixel)!=kCVReturnSuccess)return 4;
  CVPixelBufferLockBaseAddress(pixel,0);unsigned char *base=CVPixelBufferGetBaseAddress(pixel);size_t stride=CVPixelBufferGetBytesPerRow(pixel);
  for(int y=0;y<180;y++)for(int x=0;x<320;x++)for(int c=0;c<4;c++)base[y*stride+x*4+c]=colors[frame/4][c];
  CVPixelBufferUnlockBaseAddress(pixel,0);
  NSDate *deadline=[NSDate dateWithTimeIntervalSinceNow:10];
  while(!input.readyForMoreMediaData&&[deadline timeIntervalSinceNow]>0)[NSThread sleepForTimeInterval:.001];
  BOOL ok=[adaptor appendPixelBuffer:pixel withPresentationTime:CMTimeMake(frame,4)];CVPixelBufferRelease(pixel);if(!ok)return 5;
 }
 [input markAsFinished];dispatch_semaphore_t done=dispatch_semaphore_create(0);
 [writer finishWritingWithCompletionHandler:^{dispatch_semaphore_signal(done);}];
 if(dispatch_semaphore_wait(done,dispatch_time(DISPATCH_TIME_NOW,20*NSEC_PER_SEC)))return 6;
 if(writer.status!=AVAssetWriterStatusCompleted)return 7;
 AVURLAsset *asset=[AVURLAsset URLAssetWithURL:url options:nil];
 NSDictionary *metadata=@{@"duration_seconds":@(CMTimeGetSeconds(asset.duration)),@"video_tracks":@([asset tracksWithMediaType:AVMediaTypeVideo].count),@"audio_tracks":@([asset tracksWithMediaType:AVMediaTypeAudio].count),@"generator":@"System AVFoundation; original synthetic solid-color frames, no third-party assets"};
 [[NSJSONSerialization dataWithJSONObject:metadata options:NSJSONWritingPrettyPrinted error:nil] writeToFile:[folder stringByAppendingPathComponent:@"metadata.json"] atomically:YES];
 AVAssetImageGenerator *generator=[AVAssetImageGenerator assetImageGeneratorWithAsset:asset];
 generator.requestedTimeToleranceBefore=kCMTimeZero;generator.requestedTimeToleranceAfter=kCMTimeZero;
 for(int second=0;second<3;second++){
  CMTime actual=kCMTimeZero;CGImageRef image=[generator copyCGImageAtTime:CMTimeMake(second,1) actualTime:&actual error:&error];if(!image)return 8;
  NSBitmapImageRep *bitmap=[[NSBitmapImageRep alloc] initWithCGImage:image];CGImageRelease(image);
  NSData *png=[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
  [png writeToFile:[folder stringByAppendingPathComponent:[NSString stringWithFormat:@"frame-%d.png",second]] atomically:YES];
 }
 printf("Generated owned silent MP4 and three frames decoded from that MP4\n");
 return 0;
}}
